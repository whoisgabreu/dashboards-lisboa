"""
Login.

Duas colunas: à esquerda a promessa do produto, à direita o formulário.
O lado esquerdo some abaixo de 1024px — em tela pequena ninguém lê manifesto,
quer entrar. O fundo é gerado em CSS (halo + malha), sem imagem: carrega
instantâneo e nunca fica desalinhado em resolução estranha.
"""

from __future__ import annotations

import dash
from dash import Input, Output, State, callback, dcc, html

from core.auth import sign_in
from core.branding import admin_logo_data
from core.storage import authenticate, get_tenant_by_slug
from ui.icons import icon
from ui.primitives import card, checkbox, field, logo, text_input

dash.register_page(__name__, path="/login", name="Entrar", title="Entrar — V4")

V4_LOGO = admin_logo_data()

PROOF = [
    ("R$ 48,2 mi", "em mídia gerenciada"),
    ("312", "contas conectadas"),
    ("1,4 mi", "leads gerados em 2026"),
]


def _google_button():
    """
    O 'G' é desenhado inline em SVG com as cores oficiais — é o único lugar
    do produto onde uma cor não vem dos tokens, porque marca de terceiro não
    se repinta.
    """
    return html.Button(
        [
            html.Img(
                src=(
                    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E"
                    "%3Cpath fill='%23FFC107' d='M43.6 20.1H42V20H24v8h11.3c-1.6 4.7-6.1 8-11.3 8"
                    "-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4"
                    "1 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.6-.4-3.9z'/%3E"
                    "%3Cpath fill='%23FF3D00' d='m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1"
                    "l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z'/%3E"
                    "%3Cpath fill='%234CAF50' d='M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36"
                    "c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.6 39.6 16.2 44 24 44z'/%3E"
                    "%3Cpath fill='%231976D2' d='M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2"
                    "C36.9 39.7 44 34 44 24c0-1.3-.1-2.6-.4-3.9z'/%3E%3C/svg%3E"
                ),
                width="16",
                height="16",
                alt="",
                style={"display": "block"},
            ),
            html.Span("Entrar com Google"),
        ],
        className="btn btn--secondary btn--block",
        id="google-login",
        n_clicks=0,
        disabled=True,
        title="Disponível em uma próxima integração",
    )


layout = html.Div(
    [
        dcc.Location(id="login-redirect", refresh=True),
        # ---- Coluna esquerda: quem somos ---------------------------------
        html.Aside(
            [
                html.Div(className="auth__bg"),
                html.Div(logo(brand_name="V4 Company", logo_data=V4_LOGO), className="auth__aside-inner"),
                html.Div(
                    [
                        html.H1(
                            "Toda a performance das suas campanhas em uma única tela.",
                            className="auth__headline",
                        ),
                        html.P(
                            "Meta Ads e Google Ads no mesmo painel, com investimento, "
                            "leads e custo por lead atualizados — sem planilha, sem "
                            "exportação manual, sem esperar o relatório de sexta.",
                            className="auth__lede",
                        ),
                    ],
                    className="auth__aside-inner",
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(value, className="auth__proof-value"),
                                html.Div(label, className="auth__proof-label"),
                            ]
                        )
                        for value, label in PROOF
                    ],
                    className="auth__proof",
                ),
            ],
            className="auth__aside",
        ),

        # ---- Coluna direita: o formulário --------------------------------
        html.Main(
            card(
                [
                    html.Div(logo(brand_name="V4 Company", logo_data=V4_LOGO), style={"marginBottom": "26px"}),
                    html.H2("Bem-vindo de volta", className="t-page"),
                    html.P(
                        "Entre com seu usuário administrativo ou e-mail de cliente.",
                        className="t-micro",
                        style={"marginTop": "8px", "marginBottom": "26px"},
                    ),

                    field(
                        "Usuário ou e-mail",
                        text_input(
                            placeholder="admin ou voce@empresa.com.br",
                            lead_icon="user",
                            input_type="text",
                            id="login-email",
                        ),
                    ),

                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("Senha", className="field__label"),
                                    html.Span(
                                        "Recuperação em breve",
                                        className="t-micro",
                                        style={"color": "var(--ink-muted)"},
                                        title="Fluxo de recuperação ainda não configurado",
                                    ),
                                ],
                                className="row-between",
                            ),
                            text_input(
                                placeholder="••••••••••",
                                lead_icon="lock",
                                input_type="password",
                                id="login-password",
                            ),
                        ],
                        style={"marginTop": "16px"},
                    ),

                    html.Div(
                        checkbox(
                            "Manter conectado neste dispositivo",
                            checked=True,
                            id="login-remember",
                        ),
                        style={"marginTop": "16px"},
                    ),

                    html.Button(
                        [html.Span("Entrar"), icon("arrow-right", 19)],
                        id="login-submit",
                        n_clicks=0,
                        className="btn btn--primary btn--lg btn--block",
                        style={"marginTop": "22px"},
                    ),

                    html.Div(id="login-feedback", className="form-feedback", role="alert"),

                    html.P(
                        "Acesso para clientes e administradores. Solicite uma conta ao administrador.",
                        className="t-micro",
                        style={"marginTop": "24px", "textAlign": "center"},
                    ),
                ],
                className="auth__card",
            ),
            className="auth__main",
        ),
    ],
    className="auth",
)


@callback(
    Output("login-feedback", "children"),
    Output("login-feedback", "className"),
    Output("login-redirect", "href"),
    Input("login-submit", "n_clicks"),
    Input("login-password", "n_submit"),
    State("login-email", "value"),
    State("login-password", "value"),
    State("login-remember", "value"),
    State("url", "search"),
    prevent_initial_call=True,
)
def _login(_clicks, _submit, email, password, remember, search):
    user = authenticate(email, password)
    if not user:
        return "Usuário ou senha inválidos.", "form-feedback form-feedback--error", dash.no_update

    sign_in(user, remember="on" in (remember or []))
    destination = "/admin" if user["role"] == "superadmin" else "/"
    if search and search.startswith("?next="):
        requested = search.removeprefix("?next=").split("&", 1)[0]
        if requested in {"/", "/meta-ads", "/google-ads", "/campanhas"}:
            destination = requested
        elif requested.count("/") == 1:
            tenant = get_tenant_by_slug(requested.removeprefix("/"))
            if tenant and (user["role"] == "superadmin" or user.get("tenant_id") == tenant["id"]):
                destination = requested
    return "Acesso confirmado. Entrando...", "form-feedback form-feedback--success", destination
