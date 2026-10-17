"""
Dashboard multi-tenant de performance para clientes de agência.

Autenticação, tenants, identidade visual e vínculos de contas são persistidos
no schema PostgreSQL `dashboard_clientes`. Os dados de mídia vêm das APIs
oficiais da Meta e do Google Ads.

Zero JavaScript escrito à mão: os popovers abrem e fecham trocando classe, e
o clique-fora é um "scrim" transparente em tela cheia.

Rodar:
    pip install -r requirements.txt
    python app.py        ->  http://127.0.0.1:8050
"""

from __future__ import annotations

import dash
import os
from dash import ALL, Input, Output, State, callback, ctx, dcc, html
from flask import has_request_context, redirect, request

from core.auth import (
    active_tenant,
    current_user,
    impersonator,
    is_superadmin,
    select_active_tenant,
    sign_out,
    start_impersonation,
    stop_impersonation,
)
from core.branding import brand_for_request, css_variables, favicon_data_uri, style_variables
from core.data import DEFAULT_PERIOD, METRIC_KEYS, clear_cache, get_dataset
from core.storage import get_tenant_by_slug, init_db, list_tenants
from ui import shell
from ui.ad_preview import preview_card
from ui.icons import icon
from ui.platforms import platform_mark
from ui.primitives import classes

init_db()

# Sincronizacao junto com o painel: um cliente recem-cadastrado precisava que
# alguem lembrasse de abrir `python sync_worker.py` num segundo terminal, e sem
# isso ficava zerado para sempre. A trava em arquivo garante um ciclo so, mesmo
# com o worker avulso rodando em paralelo.
from sync_worker import start_background_worker  # noqa: E402

start_background_worker()

app = dash.Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    title="Painel de performance",
    update_title=None,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0"},
        {"name": "color-scheme", "content": "light"},
        {"name": "theme-color", "content": "#FFFFFF"},
    ],
)

server = app.server
server.config.update(
    SECRET_KEY=__import__("os").getenv("PULSE_SECRET_KEY", "pulse-local-change-this-secret"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=__import__("datetime").timedelta(days=30),
)


@server.before_request
def _protect_pages():
    """Protege os documentos das páginas; callbacks continuam no endpoint Dash."""
    if request.method != "GET":
        return None
    pathname = request.path.rstrip("/") or "/"
    if pathname == "/registro" and os.getenv("PULSE_ALLOW_PUBLIC_REGISTRATION", "false").lower() != "true":
        return redirect("/login")

    # Cada identificador cadastrado funciona como uma URL curta do painel.
    # Só tratamos caminhos com um segmento e um slug existente, preservando
    # todos os endpoints internos do Dash e arquivos estáticos.
    if pathname.count("/") == 1 and pathname not in {"/", "/login", "/registro", "/admin", "/convite"}:
        tenant = get_tenant_by_slug(pathname.removeprefix("/"))
        if tenant:
            user = current_user()
            if not user:
                return redirect(f"/login?next={pathname}")
            if is_superadmin(user):
                select_active_tenant(tenant["id"])
                return redirect("/")
            if user.get("tenant_id") == tenant["id"]:
                return redirect("/")
            return redirect("/")

    protected = {"/", "/meta-ads", "/google-ads", "/campanhas", "/admin"}
    if pathname not in protected:
        return None
    user = current_user()
    if not user:
        return redirect(f"/login?next={pathname}")
    if pathname == "/admin" and not is_superadmin(user):
        return redirect("/")
    return None


@server.get("/logout")
def _logout():
    sign_out()
    return redirect("/login")


@server.get("/entrar-como/<int:user_id>")
def _impersonate(user_id: int):
    """Passa a ver o produto como o acesso escolhido. Só para o master."""
    try:
        start_impersonation(user_id)
    except (PermissionError, ValueError):
        return redirect("/admin")
    clear_cache()
    return redirect("/")


@server.get("/voltar-admin")
def _stop_impersonating():
    if stop_impersonation():
        clear_cache()
        return redirect("/admin")
    return redirect("/")

def _interpolate_index(**kwargs) -> str:
    """
    Monta o documento por requisição, com a identidade do cliente.

    Duas coisas precisam existir ANTES da primeira pintura e por isso vivem
    aqui, e não na árvore React:

    * **O favicon** — é um `<link>` no `<head>`, fora do alcance do Dash.
    * **As variáveis de cor** — se fossem só no elemento raiz, a tela
      apareceria por um instante com o vermelho padrão e só depois viraria a
      cor do cliente. O `<style>` entra depois do `{%css%}` para ganhar dos
      tokens estáticos.

    Inter vem do Google Fonts com fallback para a fonte do sistema: rede
    bloqueada degrada a tipografia em vez de quebrar a página.
    """
    brand = brand_for_request()
    title = kwargs.get("title") or "Painel"
    brand_name = brand.get("name") or "V4 Company"
    if brand_name not in title:
        title = f"{title.split(' — ')[0]} — {brand_name}"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
  <head>
    {kwargs['metas']}
    <title>{title}</title>
    <link rel="icon" href="{favicon_data_uri(brand)}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    {kwargs['css']}
    <style>{css_variables(brand)}</style>
  </head>
  <body>
    {kwargs['app_entry']}
    <footer>{kwargs['config']}{kwargs['scripts']}{kwargs['renderer']}</footer>
  </body>
</html>"""


app.interpolate_index = _interpolate_index


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------

INITIAL = get_dataset(DEFAULT_PERIOD)


def _impersonation_bar():
    """
    Faixa permanente durante uma simulação.

    Sem ela é fácil esquecer que se está dentro da conta de um cliente e
    concluir que "o admin sumiu do menu". O caminho de volta fica no mesmo
    lugar do aviso.
    """
    admin = impersonator()
    if not admin:
        return None

    user = current_user()
    return html.Div(
        [
            icon("eye", 16),
            html.Span(
                [
                    "Você está vendo o painel como ",
                    html.Strong(user.get("name") if user else "cliente"),
                    html.Span(f' · {user.get("email")}' if user else "", className="impersonation__email"),
                ],
                className="impersonation__text",
            ),
            html.A("Voltar para minha conta", href="/voltar-admin", className="impersonation__exit"),
        ],
        className="impersonation",
        role="status",
    )


def _ui_pathname() -> str:
    """
    A tela que o usuário está vendo.

    `request.path` só diz isso quando é o próprio documento que está sendo
    servido. O layout chega por `/_dash-layout` e as callbacks por
    `/_dash-update-component` — requisições à parte, disparadas pela página já
    carregada, onde o caminho da tela vem no `Referer`. Sem isso o corpo da
    página resolvia a marca como se estivesse sempre em `/_dash-layout`, e o
    painel de clientes continuava pintado com a marca do último cliente.
    """
    if not has_request_context():
        return "/"
    if not request.path.startswith("/_dash"):
        return request.path
    referrer = request.referrer
    if referrer:
        from urllib.parse import urlparse

        return urlparse(referrer).path or "/"
    return "/"


def _serve_layout():
    user = current_user()
    tenant = active_tenant(user)
    pathname = _ui_pathname()
    # Mesma resolução usada no <head>, para o corpo e o favicon nunca
    # mostrarem marcas diferentes — inclusive na tela de login.
    brand = brand_for_request(pathname)
    accounts = shell.account_options(user, tenant)
    return html.Div(
        [
            _impersonation_bar(),
            dcc.Location(id="url", refresh=False),
            dcc.Store(id="period-store", data=DEFAULT_PERIOD),
            dcc.Store(id="refresh-store", data=0),
            dcc.Interval(id="auto-refresh", interval=10 * 60 * 1000, n_intervals=0),
            dcc.Store(id="sidebar-expanded", data=False),
            dcc.Store(id="account-store", data=tenant["id"] if tenant else None),
            dcc.Location(id="account-redirect", refresh=True),
            dcc.Store(id="metrics-store", storage_type="local", data=METRIC_KEYS),
            # Métricas e cores do gráfico personalizável, por navegador
            dcc.Store(id="chart-store", storage_type="local", data=None),
            html.Div(
                [
                    shell.sidebar(pathname, user=user, brand=brand, extra_nav=shell.tenant_nav(tenant)),
                    html.Div(id="drawer-scrim", n_clicks=0, className="sidebar__scrim hide"),
                    html.Div(
                        [
                            shell.topbar(
                                pathname, DEFAULT_PERIOD, INITIAL["range"], METRIC_KEYS,
                                user=user, brand=brand, accounts=accounts,
                            ),
                            html.Main(
                                dcc.Loading(
                                    dash.page_container,
                                    id="page-loading",
                                    fullscreen=True,
                                    delay_show=180,
                                    delay_hide=280,
                                    custom_spinner=html.Div(
                                        [
                                            html.Div(
                                                [platform_mark("meta", 34), platform_mark("google", 30)],
                                                className="loading-screen__brands",
                                            ),
                                            html.Div(className="loading-screen__spinner"),
                                            html.Strong("Atualizando os dados"),
                                            html.Span("Consultando Meta Ads e Google Ads..."),
                                        ],
                                        className="loading-screen",
                                    ),
                                ),
                                className="shell__content",
                            ),
                        ],
                        className="shell__main",
                    ),
                ],
                className="shell",
                id="shell",
            ),
            html.Div(
                [
                    html.Div(id="ad-preview-scrim", n_clicks=0, className="ad-preview-overlay__scrim"),
                    html.Section(
                        [
                            html.Button(
                                icon("x", 22),
                                id="ad-preview-close",
                                n_clicks=0,
                                className="btn btn--secondary btn--icon ad-preview-overlay__close",
                                **{"aria-label": "Fechar anúncio ampliado", "title": "Fechar"},
                            ),
                            html.Div(id="ad-preview-content"),
                        ],
                        className="ad-preview-overlay__card",
                        role="dialog",
                        **{"aria-modal": "true", "aria-label": "Detalhes do anúncio"},
                    ),
                ],
                id="ad-preview-overlay",
                className="ad-preview-overlay hide",
            ),
        ],
        id="app-root",
        style=style_variables(brand),
    )


app.layout = _serve_layout


# --------------------------------------------------------------------------
# Navegação
# --------------------------------------------------------------------------

@callback(
    Output("shell", "className"),
    Output({"type": "nav-link", "href": ALL}, "className"),
    Output("topbar-page", "children"),
    Output("metric-anchor", "className"),
    # A identidade visual muda de tela para tela: /admin é da agência, o resto
    # é do cliente inspecionado. Como o Dash navega sem refazer o documento,
    # quem troca as cores, a logo e o nome é esta callback.
    Output("app-root", "style"),
    Output("brand-logo", "children"),
    Output("topbar-client", "children"),
    Input("url", "pathname"),
    State({"type": "nav-link", "href": ALL}, "id"),
)
def _sync_navigation(pathname, nav_ids):
    """Um único lugar decide o que é 'a página atual' — shell, menu e topo."""
    pathname = pathname or "/"
    is_auth = pathname in {"/login", "/registro"}
    is_admin_page = pathname == "/admin"

    brand = brand_for_request(pathname)

    return (
        classes("shell", "shell--auth" if is_auth else None),
        [shell.nav_class(item["href"], pathname) for item in nav_ids],
        "Clientes" if is_admin_page else shell.PAGE_TITLES.get(pathname, "Dashboard"),
        # O seletor de métricas governa a faixa de KPIs do dashboard;
        # nas outras telas as métricas são fixas da plataforma.
        classes("pop-anchor", None if pathname == "/" and not is_admin_page else "hide"),
        style_variables(brand),
        shell.brand_logo(brand),
        brand["name"],
    )


# --------------------------------------------------------------------------
# Filtro de período
# --------------------------------------------------------------------------

@callback(
    Output("period-store", "data"),
    Output("topbar-range", "children"),
    Input("period-select", "value"),
    prevent_initial_call=True,
)
def _period(period_id):
    from core import fmt

    period_id = period_id or DEFAULT_PERIOD
    date_range = get_dataset(period_id)["range"]

    return (
        period_id,
        f'{fmt.long_date(date_range["start"])} – {fmt.long_date(date_range["end"])}',
    )


# --------------------------------------------------------------------------
# Seletor de métricas
# --------------------------------------------------------------------------

@callback(
    Output("metric-menu", "className"),
    Output("metric-scrim", "className"),
    Output("metric-menu", "children"),
    Output("metrics-store", "data"),
    Input("metric-trigger", "n_clicks"),
    Input("metric-scrim", "n_clicks"),
    Input("metric-checklist", "value"),
    Input("metric-all", "n_clicks"),
    Input("metric-none", "n_clicks"),
    State("metric-menu", "className"),
    State("metrics-store", "data"),
    prevent_initial_call=True,
)
def _metrics(_t, _s, checked, _all, _none, menu_class, selected):
    """
    Abrir, marcar, limpar e selecionar tudo — uma callback só.

    O menu NÃO fecha ao marcar uma métrica: escolher quais indicadores
    aparecem é uma tarefa de várias marcações seguidas, e fechar a cada
    clique obrigaria a reabrir doze vezes.
    """
    trigger = ctx.triggered_id
    was_open = "hide" not in (menu_class or "")
    open_menu = was_open

    if trigger == "metric-trigger":
        open_menu = not was_open
    elif trigger == "metric-scrim":
        open_menu = False
    elif trigger == "metric-all":
        selected = list(METRIC_KEYS)
    elif trigger == "metric-none":
        selected = []
    elif trigger == "metric-checklist":
        # mantém sempre a ordem canônica, não a ordem de clique
        selected = [key for key in METRIC_KEYS if key in (checked or [])]

    return (
        classes("pop", "pop--right", None if open_menu else "hide"),
        classes("scrim", None if open_menu else "hide"),
        shell.metric_menu_items(selected),
        selected,
    )


# --------------------------------------------------------------------------
# Troca de conta
# --------------------------------------------------------------------------

@callback(
    Output("account-menu", "className"),
    Output("account-scrim", "className"),
    Output("account-menu", "children"),
    Output("account-store", "data"),
    Output("account-redirect", "href"),
    # Trocar de cliente troca a identidade visual na hora. Estes três já são
    # escritos pela callback de navegação, daí o `allow_duplicate`. Eles não
    # são redundantes com o redirecionamento abaixo: o `dcc.Location` só
    # navega quando o href MUDA, então trocar de cliente duas vezes seguidas
    # na mesma tela não recarregava nada e as cores ficavam do anterior.
    Output("app-root", "style", allow_duplicate=True),
    Output("brand-logo", "children", allow_duplicate=True),
    Output("topbar-client", "children", allow_duplicate=True),
    Input("account-trigger", "n_clicks"),
    Input("account-scrim", "n_clicks"),
    Input({"type": "account-opt", "id": ALL}, "n_clicks"),
    State("account-menu", "className"),
    State("account-store", "data"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def _account_control(_t, _s, _opts, menu_class, active_id, pathname):
    trigger = ctx.triggered_id
    kind = trigger.get("type") if isinstance(trigger, dict) else trigger

    was_open = "hide" not in (menu_class or "")
    open_menu = was_open
    redirect_href = dash.no_update

    if kind == "account-trigger":
        open_menu = not was_open
    elif kind == "account-scrim":
        open_menu = False
    elif kind == "account-opt":
        active_id = int(trigger["id"])
        select_active_tenant(active_id)
        clear_cache()
        open_menu = False
        redirect_href = pathname or "/"

    user = current_user()
    tenant = active_tenant(user)
    accounts = shell.account_options(user, tenant)

    # A marca segue a MESMA regra da navegação: no painel de clientes quem
    # aparece é a agência, mesmo com um cliente selecionado no seletor.
    brand = brand_for_request(pathname)
    name = brand["name"] if tenant else "Nenhum cliente selecionado"

    return (
        classes("pop", "pop--left", None if open_menu else "hide"),
        classes("scrim", None if open_menu else "hide"),
        shell._account_menu_items(accounts, active_id),
        active_id,
        redirect_href,
        style_variables(brand),
        shell.brand_logo(brand),
        name,
    )


# --------------------------------------------------------------------------
# Menu do usuário
# --------------------------------------------------------------------------

@callback(
    Output("user-menu", "className"),
    Output("user-scrim", "className"),
    Input("user-trigger", "n_clicks"),
    Input("user-scrim", "n_clicks"),
    State("user-menu", "className"),
    prevent_initial_call=True,
)
def _user_menu(_t, _s, menu_class):
    open_menu = "hide" in (menu_class or "") and ctx.triggered_id == "user-trigger"
    return (
        classes("pop", None if open_menu else "hide"),
        classes("scrim", None if open_menu else "hide"),
    )


# --------------------------------------------------------------------------
# Gaveta da sidebar (tablet e celular)
# --------------------------------------------------------------------------

@callback(
    Output("sidebar", "className"),
    Output("drawer-scrim", "className"),
    Output("sidebar-expanded", "data"),
    Output("sidebar-resize", "title"),
    Output("sidebar-resize", "aria-label"),
    Output("sidebar-resize", "children"),
    Input("drawer-open", "n_clicks"),
    Input("drawer-close", "n_clicks"),
    Input("drawer-scrim", "n_clicks"),
    Input("sidebar-resize", "n_clicks"),
    Input("url", "pathname"),
    State("sidebar-expanded", "data"),
    prevent_initial_call=True,
)
def _drawer(_open, _close, _scrim, _resize, _path, expanded):
    # navegar também fecha a gaveta — senão o menu fica por cima da tela nova
    should_open = ctx.triggered_id == "drawer-open"
    if ctx.triggered_id == "sidebar-resize":
        expanded = not bool(expanded)
    return (
        classes("sidebar", "sidebar--compact", "sidebar--expanded" if expanded else None, "sidebar--open" if should_open else None),
        classes("sidebar__scrim", None if should_open else "hide"),
        bool(expanded),
        "Recolher menu" if expanded else "Expandir menu",
        "Recolher menu" if expanded else "Expandir menu",
        # A seta aponta para onde o menu vai
        icon("chevron-left" if expanded else "chevron-right", 19),
    )


# --------------------------------------------------------------------------
# Atualizar
# --------------------------------------------------------------------------

@callback(
    Output("refresh-store", "data"),
    Input("refresh-btn", "n_clicks"),
    Input("auto-refresh", "n_intervals"),
    State("refresh-store", "data"),
    prevent_initial_call=True,
)
def _refresh(_clicks, _intervals, tick):
    clear_cache()
    return (tick or 0) + 1


# --------------------------------------------------------------------------
# Criativo ampliado e métricas do anúncio
# --------------------------------------------------------------------------

@callback(
    Output("ad-preview-overlay", "className"),
    Output("ad-preview-content", "children"),
    Input({"type": "ad-preview-open", "ad_id": ALL}, "n_clicks"),
    Input("ad-preview-close", "n_clicks"),
    Input("ad-preview-scrim", "n_clicks"),
    State("period-store", "data"),
    prevent_initial_call=True,
)
def _ad_preview(opens, _close, _scrim, period_id):
    trigger = ctx.triggered_id
    if trigger == "ad-preview-close" or trigger == "ad-preview-scrim":
        return "ad-preview-overlay hide", dash.no_update
    if not isinstance(trigger, dict):
        return "ad-preview-overlay hide", dash.no_update

    # Ao trocar para a aba de anúncios, os botões são CRIADOS e o Dash dispara
    # a callback com n_clicks None/0. Sem esta guarda, abrir a aba abria um
    # anúncio sozinho — era o "já abre um anúncio aberto".
    if not any(opens or []):
        return dash.no_update, dash.no_update

    ad_id = str(trigger.get("ad_id") or "")
    ads = get_dataset(period_id or DEFAULT_PERIOD)["meta"]["ads"]
    ad = next((item for item in ads if str(item.get("id")) == ad_id), None)
    if not ad:
        return "ad-preview-overlay hide", dash.no_update
    return "ad-preview-overlay", preview_card(ad)


if __name__ == "__main__":
    app.run(debug=os.getenv("PULSE_DEBUG", "true").lower() == "true", port=8050)
