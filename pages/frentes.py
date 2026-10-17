"""
Frentes — investimento e resultado por frente de negócio e por plataforma.

Para clientes com mais de uma operação (ex.: assessoria e franquias). A frente vem do rótulo de cada conta de anúncio; leads da
planilha entram ao lado dos leads que as plataformas reportam, porque os dois
números contam coisas diferentes e os dois importam.
"""

from __future__ import annotations

import dash
from dash import Input, Output, callback, html

from core import fmt
from core.data import DEFAULT_PERIOD, get_dataset, get_period
from core.leads import get_leads_dataset
from core.theme import entity_color
from ui.kpi import kpi_grid
from ui.primitives import card, card_body, card_header, empty_state
from ui.shell import page_head
from ui.tables import data_table

dash.register_page(__name__, path="/frentes", name="Frentes", title="Frentes")


def _variation(current: float, previous: float) -> float:
    return (current - previous) / previous * 100 if previous else 0.0


def _kpis(frentes: list[dict]) -> list[dict]:
    result = []
    for row in (item for item in frentes if item.get("subtotal")):
        prev_cpl = row["prev_investimento"] / row["prev_leads"] if row["prev_leads"] else 0.0
        name = row["frente"]
        result.extend(
            [
                {"key": f"inv-{name}", "label": f"{name} · Investimento", "icon": "wallet",
                 "type": "currency", "good": "neutral", "value": row["investimento"],
                 "variation": _variation(row["investimento"], row["prev_investimento"]), "spark": []},
                {"key": f"leads-{name}", "label": f"{name} · Leads", "icon": "magnet",
                 "type": "int", "good": "up", "value": row["leads"],
                 "variation": _variation(row["leads"], row["prev_leads"]), "spark": []},
                {"key": f"cpl-{name}", "label": f"{name} · CPL", "icon": "user-plus",
                 "type": "currency_cents", "good": "down", "value": row["cpl"],
                 "variation": _variation(row["cpl"], prev_cpl), "spark": []},
            ]
        )
    return result


HEADERS = [
    ("Frente / plataforma", None), ("Investimento", "num"), ("Impressões", "num"), ("Cliques", "num"),
    ("CTR", "num"), ("CPC", "num"), ("Leads (plataforma)", "num"), ("CPL", "num"),
    ("Leads (planilha)", "num"), ("Custo por lead (planilha)", "num"),
]


def _cells(row: dict, sheet_leads: int | None):
    values = [
        fmt.brl(row["investimento"]), fmt.integer(row["impressoes"]), fmt.integer(row["cliques"]),
        fmt.pct(row["ctr"]), fmt.brl_cents(row["cpc"]), fmt.integer(row["leads"]),
        fmt.brl_cents(row["cpl"]) if row["leads"] else "—",
        fmt.integer(sheet_leads) if sheet_leads is not None else "—",
        fmt.brl_cents(row["investimento"] / sheet_leads) if sheet_leads else "—",
    ]
    return [html.Td(value, className="td-num td-strong" if row.get("subtotal") else "td-num") for value in values]


def _name(row: dict):
    return html.Td(
        html.Div(
            [
                html.Span(className="channel-dot", style={"background": entity_color(row["canal"])})
                if row.get("canal") else None,
                html.Span(row["nome"], className="td-name__text", title=row["nome"],
                          style={"fontWeight": "600"} if row.get("subtotal") else {"paddingLeft": "4px"}),
            ],
            className="td-name",
        )
    )


def _breakdown(frentes: list[dict], sheet_by_frente: dict, sheet_configured: bool):
    rows = []
    for row in frentes:
        sheet = sheet_by_frente.get(row["frente"], 0) if (row.get("subtotal") and sheet_configured) else None
        rows.append(html.Tr([_name(row), *_cells(row, sheet)]))

    subtotals = [row for row in frentes if row.get("subtotal")]
    if len(subtotals) > 1:
        total = {key: sum(row[key] for row in subtotals)
                 for key in ("investimento", "impressoes", "cliques", "leads")}
        total.update(
            {
                "nome": "Total", "canal": None, "subtotal": True,
                "ctr": total["cliques"] / total["impressoes"] * 100 if total["impressoes"] else 0.0,
                "cpc": total["investimento"] / total["cliques"] if total["cliques"] else 0.0,
                "cpl": total["investimento"] / total["leads"] if total["leads"] else 0.0,
            }
        )
        sheet = sum(sheet_by_frente.values()) if sheet_configured else None
        rows.append(html.Tr([_name(total), *_cells(total, sheet)], className="table-total"))

    return html.Div(
        html.Table(
            [
                html.Thead(html.Tr([
                    html.Th(html.Span(label, className="th-btn th-btn--num" if kind else "th-btn"))
                    for label, kind in HEADERS
                ])),
                html.Tbody(rows),
            ],
            className="table",
        ),
        className="table-scroll",
    )


def _body(period_id: str):
    data = get_dataset(period_id)
    period = get_period(period_id)
    frentes = data.get("frentes") or []
    if not frentes:
        return [
            page_head("Frentes", [("Visão geral", None), ("Frentes", None)], glyph="chart-column"),
            card(empty_state(
                "Nenhuma frente cadastrada",
                "Rotule as contas de anúncio com a frente (manage_sources.py conta …) para ver esta visão.",
                glyph="chart-column",
            )),
        ]

    leads = get_leads_dataset(period_id)
    return [
        page_head(
            "Frentes",
            [("Visão geral", None), ("Frentes", None)],
            description=(
                f'{fmt.long_date(data["range"]["start"])} a {fmt.long_date(data["range"]["end"])} · '
                "investimento e resultado de cada frente, por plataforma"
            ),
            glyph="chart-column",
        ),
        kpi_grid(_kpis(frentes), compare_label=period["compare"]),
        card(
            [
                card_header(
                    "Frente × plataforma",
                    subtitle="Leads (plataforma) = conversões do Google Ads + leads da Meta. "
                             "Leads (planilha) = linhas registradas nas planilhas das LPs.",
                    lead_icon="chart-column",
                ),
                _breakdown(frentes, leads.get("by_frente", {}), leads.get("configured", False)),
            ],
            style={"marginBottom": "16px"},
        ),
        data_table(
            "frentes-campanhas",
            period_id,
            "Campanhas por frente",
            subtitle="Todas as contas · busque pelo nome da frente para filtrar",
        ),
        card(
            card_body(
                html.Ul(
                    [
                        html.Li("Os números de plataforma vêm das APIs oficiais (Google Ads e Meta Marketing API) "
                                "e são atualizados a cada 10 minutos."),
                        html.Li("Leads (plataforma) e Leads (planilha) medem coisas diferentes: a plataforma conta "
                                "a conversão que ela registrou; a planilha conta quem de fato preencheu o formulário. "
                                "Diferença grande entre os dois aponta problema de rastreamento."),
                        html.Li("Negociação e venda ficam para a V2 (dependem da integração com o CRM)."),
                    ],
                    className="t-micro",
                    style={"margin": "0", "paddingLeft": "18px", "lineHeight": "1.7"},
                )
            ),
            style={"marginTop": "16px"},
        ),
    ]


def layout():
    return html.Div(_body(DEFAULT_PERIOD), id="page-frentes", className="anim-up")


@callback(
    Output("page-frentes", "children"),
    Input("period-store", "data"),
    Input("refresh-store", "data"),
    prevent_initial_call=True,
)
def _reload(period_id, _tick):
    return _body(period_id or DEFAULT_PERIOD)
