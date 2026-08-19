"""
Tema dos gráficos — o mesmo design system dos tokens CSS, em Python.

As cores das séries NÃO são fixas: elas são derivadas da cor do cliente
ativo (ver `core/branding.py`), então trocar a cor no admin repinta gráfico,
sparkline e funil, não só o botão.

As séries são nomeadas por PAPEL (`primary`, `secondary`, `tertiary`) e não
por cor. Chamar de "azul" o que hoje pode ser roxo, verde ou laranja seria
mentir no nome da variável — e foi exatamente o que travou o whitelabel.

O que a cor do cliente não governa, de propósito:

* **Verde e vermelho de status.** Se a marca é verde, "caiu 8%" não pode
  aparecer em verde.
* **A grade e os eixos.** São cinza recessivo em qualquer marca; grade
  colorida disputa atenção com o dado.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

from core.branding import DEFAULT_PRIMARY, DEFAULT_SECONDARY, brand_palette

# --------------------------------------------------------------------------
# Cores que não dependem da marca
# --------------------------------------------------------------------------

STATUS = {
    "positive": "#16A34A",
    "negative": "#E5001A",
    "warning": "#B45309",
}

INK = {
    "primary": "#0B0B0D",
    "secondary": "#52565E",
    "muted": "#767B84",
    "faint": "#9AA0A9",
}

CHROME = {
    "grid": "#EEF0F2",
    "axis": "#E6E7EA",
    "surface": "#FFFFFF",
    "spike": "#C4C8CE",
}

FONT = "Inter, system-ui, -apple-system, Segoe UI, sans-serif"

# Entidade → papel na paleta. A cor segue a ENTIDADE, nunca a posição no
# ranking: se um filtro tira uma campanha, as demais não trocam de cor.
ENTITY_ROLE = {
    "investimento": "primary",
    "cpl": "primary",
    "meta": "primary",
    "receita": "secondary",
    "leads": "secondary",
    "organico": "secondary",
    "cliques": "tertiary",
    "google": "tertiary",
    "outros": "neutral",
}


# --------------------------------------------------------------------------
# Paleta do cliente ativo
# --------------------------------------------------------------------------

_REQUEST_CACHE_KEY = "_pulse_brand_colors"


def _active_brand_colors() -> tuple[str, str]:
    """
    Cores do cliente em contexto. Fora de um request (import, script, teste)
    devolve o padrão em vez de estourar — desenhar um gráfico não pode
    depender de haver alguém logado.

    O resultado é memorizado NO REQUEST (`flask.g`). Sem isso cada chamada
    de `series_color`/`entity_color` reabria a sessão e o tenant no banco —
    uma célula de tabela por vez, 124 conexões e 10 segundos para montar a
    tela do Meta. A marca não muda no meio de uma requisição, então uma
    resolução por requisição basta.
    """
    try:
        from flask import g, has_request_context

        if not has_request_context():
            return DEFAULT_PRIMARY, DEFAULT_SECONDARY

        cached = getattr(g, _REQUEST_CACHE_KEY, None)
        if cached is not None:
            return cached

        colors = _resolve_brand_colors()
        setattr(g, _REQUEST_CACHE_KEY, colors)
        return colors
    except Exception:
        return DEFAULT_PRIMARY, DEFAULT_SECONDARY


def _resolve_brand_colors() -> tuple[str, str]:
    try:
        from core.auth import active_tenant, current_user, is_superadmin

        user = current_user()
        if not user:
            return DEFAULT_PRIMARY, DEFAULT_SECONDARY
        if is_superadmin(user):
            # O master vê os dados do cliente selecionado, então os gráficos
            # usam a cor DESSE cliente — é o que ele mostra na reunião.
            tenant = active_tenant(user)
            if tenant:
                return (
                    tenant.get("primary_color") or DEFAULT_PRIMARY,
                    tenant.get("secondary_color") or DEFAULT_SECONDARY,
                )
            return DEFAULT_PRIMARY, DEFAULT_SECONDARY
        return (
            user.get("primary_color") or DEFAULT_PRIMARY,
            user.get("secondary_color") or DEFAULT_SECONDARY,
        )
    except Exception:
        return DEFAULT_PRIMARY, DEFAULT_SECONDARY


def palette() -> dict:
    """Paleta de gráfico do cliente ativo, por papel."""
    primary, secondary = _active_brand_colors()
    resolved = brand_palette(primary, secondary)
    series = resolved["series"]
    return {
        "primary": series[0],
        "secondary": series[1],
        "tertiary": series[2],
        "neutral": series[3],
        "ordinal": resolved["ordinal"],
    }


def series_color(role: str) -> str:
    """Cor de um papel de série (`primary`, `secondary`, `tertiary`, `neutral`)."""
    return palette().get(role, palette()["primary"])


def entity_color(key: str | None) -> str:
    """Cor de uma entidade nomeada (investimento, receita, meta, google…)."""
    return series_color(ENTITY_ROLE.get(key or "", "neutral"))


def ordinal_ramp() -> list[str]:
    """Rampa de matiz única do funil, na cor do cliente."""
    return palette()["ordinal"]


# --------------------------------------------------------------------------
# Template Plotly
# --------------------------------------------------------------------------

def _build_template() -> go.layout.Template:
    template = go.layout.Template()

    template.layout = go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=11, color=INK["muted"]),
        # Sem legenda embutida: a legenda é HTML, ao lado do título do card,
        # onde cabe o valor em texto junto do swatch.
        showlegend=False,
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            bordercolor=CHROME["axis"],
            font=dict(family=FONT, size=11, color=INK["primary"]),
            align="left",
        ),
        xaxis=dict(
            showgrid=False,          # grade só na horizontal — vertical vira ruído
            zeroline=False,
            showline=False,
            ticks="",
            tickangle=0,             # rótulo girado come altura e desalinha o card
            tickfont=dict(size=10, color=INK["muted"]),
            automargin=False,
            showspikes=True,         # crosshair no hover
            spikemode="across",
            spikesnap="cursor",
            spikecolor=CHROME["spike"],
            spikethickness=1,
            spikedash="solid",
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=CHROME["grid"],
            gridwidth=1,
            zeroline=False,
            showline=False,
            ticks="",
            tickfont=dict(size=10, color=INK["muted"]),
            automargin=False,
        ),
    )

    return template


pio.templates["pulse"] = _build_template()
pio.templates.default = "pulse"


# Config padrão do dcc.Graph: sem barra de ferramentas, responsivo.
GRAPH_CONFIG = {
    "displayModeBar": False,
    "responsive": True,
    "scrollZoom": False,
    "doubleClick": False,
    "showTips": False,
    "locale": "pt-br",
}
