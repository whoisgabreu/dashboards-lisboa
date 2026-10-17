"""Leads de landing pages lidos de planilhas Google.

Cada tenant pode ter abas de planilha cadastradas em `tenant_lead_sources`
(uma aba = uma LP). A sincronização lê a aba inteira e grava só data, LP e
UTMs em `lead_entries`. Dados pessoais (nome, e-mail, telefone, CNPJ) e as
observações do comercial nunca saem da planilha.

Acesso à planilha, nesta ordem:

1. `GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE` configurado: Sheets API com a conta
   de serviço (a planilha precisa estar compartilhada com o e-mail dela).
2. Sem conta de serviço: exportação CSV pelo link da planilha, que só
   funciona enquanto ela estiver aberta para "qualquer pessoa com o link".
"""

from __future__ import annotations

import csv
import io
import logging
import os
import re
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

from core.storage import (
    get_lead_entries,
    lead_entries_summary,
    list_lead_sources,
    media_campaign_names,
    replace_lead_entries,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
NO_UTM = "Sem UTM"


class LeadSourceError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Leitura da planilha
# --------------------------------------------------------------------------

def _service_account_token() -> str | None:
    path = os.getenv("GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE", "").strip()
    if not path:
        return None
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_file(path, scopes=[SHEETS_SCOPE])
    credentials.refresh(Request())
    return credentials.token


def _tab_gids(sheet_id: str) -> dict[str, str]:
    """Nome da aba -> gid, lido da visualização pública da planilha."""
    response = requests.get(f"https://docs.google.com/spreadsheets/d/{sheet_id}/htmlview", timeout=30)
    if not response.ok:
        return {}
    return dict(re.findall(r'name:\s*"([^"]+)"[^}]*?gid:\s*"?(\d+)', response.text))


def fetch_tab(sheet_id: str, tab: str) -> list[list[str]]:
    token = _service_account_token()
    if token:
        response = requests.get(
            f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{requests.utils.quote(tab)}",
            headers={"Authorization": f"Bearer {token}"},
            params={"valueRenderOption": "FORMATTED_VALUE"},
            timeout=45,
        )
        if not response.ok:
            raise LeadSourceError(f"Sheets API recusou a aba {tab!r}: HTTP {response.status_code}")
        return response.json().get("values", [])

    # A exportação por gid devolve o texto cru de cada célula. O endpoint
    # `gviz` (que aceita o nome da aba) infere um tipo por coluna e ZERA as
    # células do tipo minoritário — numa coluna utm_campaign com IDs
    # numéricos, os nomes de campanha em texto sumiam sem aviso.
    gid = _tab_gids(sheet_id).get(tab)
    if gid is None:
        raise LeadSourceError(
            f"Aba {tab!r} não encontrada. A planilha precisa estar acessível pelo link "
            "ou compartilhada com a conta de serviço."
        )
    response = requests.get(
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export",
        params={"format": "csv", "gid": gid},
        timeout=45,
    )
    if not response.ok or "text/csv" not in response.headers.get("content-type", ""):
        raise LeadSourceError(f"Não foi possível exportar a aba {tab!r} (HTTP {response.status_code}).")
    return list(csv.reader(io.StringIO(response.content.decode("utf-8"))))


# --------------------------------------------------------------------------
# Normalização
# --------------------------------------------------------------------------

_BR_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})")
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_SOURCE = re.compile(r"^[a-z0-9_.\-]{1,40}$")
# Telefone com separador ("91234-5678", "9123 45678") ou celular brasileiro
# colado (DDD + 9 + 8 dígitos). ID de campanha do Google também tem 11
# dígitos, então dígito puro só cai fora quando tem exatamente cara de celular.
_PHONE = re.compile(r"\d{4,5}[-\s.]\d{4}\b|^\(?[1-9]{2}\)?\s?9\d{8}$")


def parse_date(value: str | None) -> str | None:
    value = (value or "").strip()
    for pattern, order in ((_BR_DATE, "dmy"), (_ISO_DATE, "ymd")):
        match = pattern.match(value)
        if not match:
            continue
        a, b, c = (int(part) for part in match.groups())
        day, month, year = (a, b, c) if order == "dmy" else (c, b, a)
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    return None


def _clean_utm(value: str | None) -> str | None:
    """UTM vazia vira None; qualquer coisa com cara de dado pessoal também."""
    value = (value or "").strip()
    if not value or "@" in value or _PHONE.search(value):
        return None
    return value[:120]


def _clean_source(value: str | None) -> str | None:
    value = (_clean_utm(value) or "").lower()
    if not value:
        return None
    # Linha desalinhada na planilha joga texto livre na coluna da UTM.
    return value if _SOURCE.fullmatch(value) else "(valor inválido)"


def _has_content(row: list[str], skip: set[int]) -> bool:
    return any((cell or "").strip() for index, cell in enumerate(row) if index not in skip)


def parse_tab(rows: list[list[str]], *, tenant_id: int, sheet_id: str, tab: str, lp: str, frente: str | None):
    """Linhas da aba -> (leads sem dado pessoal, quantidade de linhas sem data)."""
    if not rows:
        return [], 0
    header = [(cell or "").strip().lower() for cell in rows[0]]

    def column(*names):
        for name in names:
            if name in header:
                return header.index(name)
        return None

    date_col = column("date/time", "data", "data/hora")
    utm = {key: column(key) for key in ("utm_source", "utm_medium", "utm_campaign", "utm_term")}
    click_cols = [index for index in (column("gclid"), column("fbclid")) if index is not None]
    # Colunas preenchidas por fórmula/rotina (ex.: "VENDA?") não fazem a
    # linha existir; só conteúdo de verdade conta.
    ignore = {index for index in (column("tipo"),) if index is not None}

    def cell(row, index):
        return row[index] if index is not None and index < len(row) else ""

    now = datetime.now(UTC).isoformat(timespec="seconds")
    leads, undated = [], 0
    for number, row in enumerate(rows[1:], start=2):
        if not _has_content(row, ignore):
            continue
        lead_date = parse_date(cell(row, date_col))
        if not lead_date:
            # Linha deslocada: a data às vezes está uma ou duas células à direita.
            lead_date = next((parse_date(value) for value in row[:3] if parse_date(value)), None)
        if not lead_date:
            undated += 1
            continue
        leads.append(
            {
                "tenant_id": tenant_id, "sheet_id": sheet_id, "tab": tab, "row_number": number,
                "lead_date": lead_date, "lp": lp, "frente": frente,
                "utm_source": _clean_source(cell(row, utm["utm_source"])),
                "utm_medium": _clean_source(cell(row, utm["utm_medium"])),
                "utm_campaign": _clean_utm(cell(row, utm["utm_campaign"])),
                "utm_term": _clean_utm(cell(row, utm["utm_term"])),
                "has_click_id": 1 if any((cell(row, index) or "").strip() for index in click_cols) else 0,
                "updated_at": now,
            }
        )
    return leads, undated


def sync_leads(tenant: dict) -> int | None:
    """Relê todas as abas do tenant. None quando ele não tem planilha."""
    sources = list_lead_sources(tenant.get("id"))
    if not sources:
        return None
    total = 0
    errors = []
    for source in sources:
        try:
            rows = fetch_tab(source["sheet_id"], source["tab"])
        except (LeadSourceError, requests.RequestException) as exc:
            # Uma aba fora do ar não apaga o que já estava gravado dela.
            errors.append(f"{source['tab']}: {exc}")
            continue
        leads, undated = parse_tab(
            rows, tenant_id=tenant["id"], sheet_id=source["sheet_id"], tab=source["tab"],
            lp=source["lp"], frente=source.get("frente"),
        )
        if undated:
            logger.info("%s: %s linhas sem data reconhecível ignoradas", source["tab"], undated)
        total += replace_lead_entries(tenant["id"], source["sheet_id"], source["tab"], leads)
    if errors:
        raise LeadSourceError("; ".join(errors))
    return total


# --------------------------------------------------------------------------
# Leitura para as telas
# --------------------------------------------------------------------------

def _campaign_label(value: str | None, campaigns: dict[str, dict]) -> tuple[str, str | None]:
    if not value:
        return NO_UTM, None
    if value.startswith("{") and value.endswith("}"):
        return f"Parâmetro não preenchido {value}", None
    known = campaigns.get(value)
    if known and known.get("nome"):
        return known["nome"], known.get("canal")
    return value, None


def _group(rows: list[dict], key, total: int, extra=None) -> list[dict]:
    counter = Counter(key(row) for row in rows)
    result = []
    for name, count in counter.most_common():
        item = {"id": name, "nome": name, "leads": count, "share": count / total * 100 if total else 0.0}
        if extra:
            item.update(extra(name))
        result.append(item)
    return result


def leads_for_range(tenant_id: int | None, start: date, end: date) -> dict:
    empty = {
        "configured": False, "total": 0, "previous_total": 0, "series": [], "by_lp": [],
        "by_source": [], "by_campaign": [], "by_frente": {}, "sources": [], "summary": {},
    }
    if not tenant_id:
        return empty
    sources = list_lead_sources(tenant_id)
    if not sources:
        return empty

    days = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    rows = get_lead_entries(tenant_id, start.isoformat(), end.isoformat())
    previous = get_lead_entries(tenant_id, previous_start.isoformat(), previous_end.isoformat())
    campaigns = media_campaign_names(tenant_id)
    total = len(rows)

    per_day = Counter(row["lead_date"] for row in rows)
    series = []
    current = start
    while current <= end:
        series.append({"date": current.isoformat(), "leads": per_day.get(current.isoformat(), 0)})
        current += timedelta(days=1)

    lp_frente = {source["lp"]: source.get("frente") for source in sources}
    previous_by_lp = Counter(row["lp"] for row in previous)
    by_lp = _group(
        rows, lambda row: row["lp"], total,
        lambda name: {"frente": lp_frente.get(name) or "—", "anterior": previous_by_lp.get(name, 0)},
    )
    # LP cadastrada sem lead no período continua aparecendo, com zero: some
    # da tabela parece "integração quebrada", não "LP sem lead".
    present = {row["nome"] for row in by_lp}
    by_lp.extend(
        {"id": lp, "nome": lp, "leads": 0, "share": 0.0, "frente": lp_frente.get(lp) or "—",
         "anterior": previous_by_lp.get(lp, 0)}
        for lp in dict.fromkeys(source["lp"] for source in sources) if lp not in present
    )

    by_source = _group(
        rows,
        lambda row: " / ".join(part for part in (row["utm_source"], row["utm_medium"]) if part) or NO_UTM,
        total,
    )

    labelled = defaultdict(lambda: {"canal": None, "lps": Counter()})
    for row in rows:
        name, channel = _campaign_label(row["utm_campaign"], campaigns)
        labelled[name]["canal"] = labelled[name]["canal"] or channel
        labelled[name]["lps"][row["lp"]] += 1
    by_campaign = _group(
        rows, lambda row: _campaign_label(row["utm_campaign"], campaigns)[0], total,
        lambda name: {
            "canal": labelled[name]["canal"],
            "lp": ", ".join(lp for lp, _ in labelled[name]["lps"].most_common()),
        },
    )

    by_frente = Counter((row["frente"] or "—") for row in rows)
    return {
        "configured": True,
        "total": total,
        "previous_total": len(previous),
        "with_click_id": sum(1 for row in rows if row["has_click_id"]),
        "series": series,
        "by_lp": by_lp,
        "by_source": by_source,
        "by_campaign": by_campaign,
        "by_frente": dict(by_frente),
        "sources": sources,
        "summary": lead_entries_summary(tenant_id),
    }


def get_leads_dataset(period_id: str, tenant_id: int | None = None) -> dict:
    """Mesmo período (e mesmas datas) que o resto do painel usa."""
    from core.auth import active_tenant
    from core.data import get_dataset

    data = get_dataset(period_id, tenant_id)
    tenant_id = data.get("tenant_id") or (active_tenant() or {}).get("id")
    result = leads_for_range(
        tenant_id, date.fromisoformat(data["range"]["start"]), date.fromisoformat(data["range"]["end"])
    )
    result["range"] = data["range"]
    result["period"] = data["period"]
    return result
