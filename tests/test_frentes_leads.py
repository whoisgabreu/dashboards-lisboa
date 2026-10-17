from datetime import date

from core.data import _frentes, _series_from_storage
from core.leads import _campaign_label, parse_date, parse_tab


HEADER = [
    "Date/Time", "Seu nome completo", "E-mail", "Telefone", "CNPJ", "gclid", "fbclid",
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "OBSERVAÇÃO", "Tipo",
]


def _parse(rows):
    return parse_tab([HEADER, *rows], tenant_id=1, sheet_id="s", tab="LP X", lp="LP X", frente="Assessoria")


def test_parse_date_formats_from_the_sheets():
    assert parse_date("08/10/2026 08:59") == "2026-10-08"
    assert parse_date("19/01/2026") == "2026-01-19"
    assert parse_date("2026-08-04T08:55:25.734-03:00") == "2026-08-04"
    assert parse_date("2026-09-30 14:50:18") == "2026-09-30"
    assert parse_date("31/02/2026") is None
    assert parse_date("Matheus: descartado") is None


def test_parse_tab_never_keeps_personal_data():
    leads, undated = _parse([
        ["08/10/2026", "Fulana de Tal", "fulana@empresa.com", "11 91234-5678", "12.345.678/0001-90",
         "abc", "", "google", "cpc", "20987654321", "lgpd", "ligou 2x", ""],
    ])
    assert undated == 0
    stored = " ".join(str(value) for value in leads[0].values())
    for secret in ("Fulana", "fulana@", "91234", "12.345", "ligou"):
        assert secret not in stored
    assert leads[0]["utm_campaign"] == "20987654321"
    assert leads[0]["has_click_id"] == 1


def test_parse_tab_skips_formula_only_rows_and_counts_undated():
    leads, undated = _parse([
        ["", "", "", "", "", "", "", "", "", "", "", "", "VENDA?"],
        ["sem data", "Beltrano", "", "", "", "", "", "", "", "", "", "", ""],
        # linha deslocada: a data foi parar na segunda célula
        ["", "18/02/2026", "x", "", "", "", "", "google", "cpc", "{campaignname}", "", "", ""],
    ])
    assert undated == 1
    assert [lead["lead_date"] for lead in leads] == ["2026-02-18"]


def test_utm_that_looks_like_personal_data_is_dropped():
    leads, _ = _parse([["08/10/2026", "", "", "", "", "", "", "joão:", "", "a@b.com", "11 91234-5678", "", ""]])
    assert leads[0]["utm_source"] == "(valor inválido)"
    assert leads[0]["utm_campaign"] is None
    assert leads[0]["utm_term"] is None


def test_campaign_label_uses_google_campaign_names():
    names = {"20987654321": {"nome": "3 - Busca Institucional", "canal": "google"}}
    assert _campaign_label("20987654321", names) == ("3 - Busca Institucional", "google")
    assert _campaign_label("{campaignname}", names)[0].startswith("Parâmetro não preenchido")
    assert _campaign_label(None, names)[0] == "Sem UTM"


def _account_row(account, day, spend, leads=0):
    return {"level": "account", "account_id": account, "metric_date": day, "investimento": spend,
            "receita": 0, "impressoes": 100, "cliques": 10, "leads": leads, "conversoes": leads, "alcance": 0}


def test_daily_series_sums_every_account_of_the_platform():
    rows = [_account_row("act_1", "2026-10-01", 50), _account_row("act_2", "2026-10-01", 30)]
    series = _series_from_storage(rows, date(2026, 10, 1), date(2026, 10, 1))
    assert series[0]["investimento"] == 80
    assert series[0]["impressoes"] == 200


def test_frentes_split_by_account_label():
    accounts = (("meta", "act_1", "Assessoria"), ("google", "123", "Assessoria"), ("meta", "act_2", "Franchising"))
    meta = {"by_account": {"act_1": {"investimento": 10, "leads": 1}, "act_2": {"investimento": 70, "leads": 7}},
            "by_account_previous": {}}
    google = {"by_account": {"123": {"investimento": 40, "cliques": 20, "leads": 4}}, "by_account_previous": {}}
    rows = _frentes(accounts, meta, google)
    subtotals = {row["frente"]: row for row in rows if row.get("subtotal")}
    assert subtotals["Assessoria"]["investimento"] == 50
    assert subtotals["Assessoria"]["leads"] == 5
    assert subtotals["Assessoria"]["cpl"] == 10
    assert subtotals["Franchising"]["investimento"] == 70
    assert len([row for row in rows if not row.get("subtotal")]) == 3


def test_google_campaign_ids_survive_but_glued_mobile_numbers_do_not():
    leads, _ = _parse([
        ["08/10/2026", "", "", "", "", "", "", "google", "cpc", "21234567890", "11987654321", "", ""],
    ])
    assert leads[0]["utm_campaign"] == "21234567890"
    assert leads[0]["utm_term"] is None
