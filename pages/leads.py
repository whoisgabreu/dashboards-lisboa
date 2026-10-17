"""
Leads — quem preencheu o formulário de cada landing page.

A fonte é a planilha de leads do cliente (uma aba por LP), não a conversão
reportada pela plataforma. O painel guarda só data, LP e UTMs: nome, e-mail,
telefone e CNPJ continuam só na planilha.
"""

from __future__ import annotations

import dash
from dash import Input, Output, callback, html

from core import fmt
from core.data import DEFAULT_PERIOD, get_period
from core.leads import NO_UTM, get_leads_dataset
from core.theme import series_color
from ui import charts
from ui.kpi import kpi_grid
from ui.primitives import badge, card, card_body, empty_state
from ui.shell import page_head
from ui.tables import data_table

dash.register_page(__name__, path="/leads", name="Leads", title="Leads")


def _variation(current: float, previous: float) -> float:
    return (current - previous) / previous * 100 if previous else 0.0


def _kpis(data: dict) -> list[dict]:
    metrics = [
        {"key": "leads", "label": "Leads no período", "icon": "magnet", "type": "int", "good": "up",
         "value": data["total"], "variation": _variation(data["total"], data["previous_total"]),
         "spark": [row["leads"] for row in data["series"]][-12:]},
    ]
    metrics.extend(
        {"key": f"lp-{row['nome']}", "label": row["nome"], "icon": "file-text", "type": "int", "good": "up",
         "value": row["leads"], "variation": _variation(row["leads"], row["anterior"]), "spark": []}
        for row in data["by_lp"]
    )
    return metrics


def _quality(data: dict):
    """O que o número esconde: lead sem UTM não tem campanha para creditar."""
    total = data["total"]
    no_campaign = next((row["leads"] for row in data["by_campaign"] if row["nome"] == NO_UTM), 0)
    placeholders = sum(row["leads"] for row in data["by_campaign"] if row["nome"].startswith("Parâmetro"))
    summary = data.get("summary") or {}
    items = [
        badge(f"{fmt.integer(no_campaign)} de {fmt.integer(total)} sem utm_campaign",
              "warning" if total and no_campaign / total > 0.3 else "neutral", dot=True),
        badge(f"{fmt.integer(data.get('with_click_id', 0))} com gclid/fbclid", "neutral", dot=True),
    ]
    if placeholders:
        items.append(badge(f"{fmt.integer(placeholders)} com parâmetro de UTM não preenchido", "warning", dot=True))
    if summary.get("last_date"):
        items.append(badge(f"Último lead na planilha: {fmt.long_date(summary['last_date'])}", "neutral"))
    return html.Div(items, className="row gap-2", style={"flexWrap": "wrap", "marginBottom": "16px"})


def _body(period_id: str):
    data = get_leads_dataset(period_id)
    period = get_period(period_id)
    if not data.get("configured"):
        return [
            page_head("Leads", [("Visão geral", None), ("Leads", None)], glyph="magnet"),
            card(empty_state(
                "Nenhuma planilha de leads cadastrada",
                "Cadastre as abas da planilha (manage_sources.py planilha …) para ver os leads por LP e origem.",
                glyph="magnet",
            )),
        ]

    return [
        page_head(
            "Leads",
            [("Visão geral", None), ("Leads", None)],
            description=(
                f'{fmt.long_date(data["range"]["start"])} a {fmt.long_date(data["range"]["end"])} · '
                "leads registrados nas planilhas das landing pages"
            ),
            glyph="magnet",
        ),
        kpi_grid(_kpis(data), compare_label=period["compare"]),
        _quality(data),
        html.Div(
            charts.chart_card(
                "Leads por dia",
                figure=charts.daily_bars(data["series"], "leads", series_color("primary"), "Leads"),
                subtitle=f'{fmt.integer(data["total"])} no período, todas as LPs',
            ),
            style={"marginBottom": "16px"},
        ),
        html.Div(
            data_table("leads-lp", period_id, "Por landing page",
                       subtitle="Cada aba da planilha é uma LP"),
            style={"marginBottom": "16px"},
        ),
        html.Div(
            data_table("leads-origem", period_id, "Por origem",
                       subtitle="utm_source e utm_medium que chegaram com o lead"),
            style={"marginBottom": "16px"},
        ),
        data_table(
            "leads-campanha",
            period_id,
            "Por campanha",
            subtitle="utm_campaign; IDs numéricos do Google Ads aparecem com o nome da campanha",
        ),
        card(
            card_body(
                html.P(
                    "Privacidade: o painel lê a planilha e guarda apenas data, LP e UTMs de cada lead. "
                    "Nome, e-mail, telefone, CNPJ e observações do comercial não são copiados.",
                    className="t-micro",
                    style={"margin": "0"},
                )
            ),
            style={"marginTop": "16px"},
        ),
    ]


def layout():
    return html.Div(_body(DEFAULT_PERIOD), id="page-leads", className="anim-up")


@callback(
    Output("page-leads", "children"),
    Input("period-store", "data"),
    Input("refresh-store", "data"),
    prevent_initial_call=True,
)
def _reload(period_id, _tick):
    return _body(period_id or DEFAULT_PERIOD)
