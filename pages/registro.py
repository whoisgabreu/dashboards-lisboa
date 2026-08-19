"""Cadastro público de uma empresa e seu primeiro gestor."""

from __future__ import annotations

import os

import dash
from dash import Input, Output, State, callback, dcc, html

from core.auth import sign_in
from core.storage import authenticate, create_tenant
from ui.icons import icon
from ui.primitives import card, field, logo, text_input


dash.register_page(__name__, path="/registro", name="Criar conta", title="Criar conta")


layout = html.Div(
    [
        dcc.Location(id="register-redirect", refresh=True),
        html.Aside(
            [
                html.Div(className="auth__bg"),
                html.Div(logo(), className="auth__aside-inner"),
                html.Div(
                    [
                        html.Span("COMECE COM UMA BASE ORGANIZADA", className="eyebrow"),
                        html.H1(
                            "Seu painel, com a identidade da sua empresa.",
                            className="auth__headline",
                        ),
                        html.P(
                            "Crie o ambiente da sua equipe agora. A marca, as cores e os "
                            "acessos podem ser administrados de forma independente para cada cliente.",
                            className="auth__lede",
                        ),
                        html.Div(
                            [
                                html.Div([icon("shield-check", 20), html.Span("Dados separados por cliente")]),
                                html.Div([icon("palette", 20), html.Span("Identidade visual personalizável")]),
                                html.Div([icon("users", 20), html.Span("Acessos gerenciados")]),
                            ],
                            className="auth__benefits",
                        ),
                    ],
                    className="auth__aside-inner",
                ),
                html.Div(
                    "Você será o gestor principal deste novo ambiente.",
                    className="auth__proof-label",
                    style={"position": "relative"},
                ),
            ],
            className="auth__aside",
        ),
        html.Main(
            card(
                [
                    html.Div(logo(), style={"marginBottom": "22px"}),
                    html.H2("Criar sua conta", className="t-page"),
                    html.P(
                        "Cadastre a empresa e o responsável pelo painel.",
                        className="t-micro",
                        style={"marginTop": "8px", "marginBottom": "22px"},
                    ),
                    html.Div(
                        [
                            field(
                                "Empresa",
                                text_input("Nome da empresa", "building-2", id="register-company"),
                            ),
                            field(
                                "Identificador",
                                text_input("minha-empresa", "link-2", id="register-slug"),
                                hint="Use letras minúsculas, números e hífens.",
                            ),
                        ],
                        className="form-grid form-grid--2",
                    ),
                    field(
                        "Seu nome",
                        text_input("Nome completo", "user", id="register-name"),
                        className="form-space",
                    ),
                    field(
                        "E-mail",
                        text_input("voce@empresa.com.br", "mail", "email", id="register-email"),
                        className="form-space",
                    ),
                    html.Div(
                        [
                            field("Senha", text_input("Mínimo de 8 caracteres", "lock", "password", id="register-password")),
                            field("Confirmar senha", text_input("Repita a senha", "lock", "password", id="register-confirm")),
                        ],
                        className="form-grid form-grid--2 form-space",
                    ),
                    html.Button(
                        [html.Span("Criar conta"), icon("arrow-right", 19)],
                        id="register-submit",
                        n_clicks=0,
                        className="btn btn--primary btn--lg btn--block",
                        style={"marginTop": "22px"},
                    ),
                    html.Div(id="register-feedback", className="form-feedback", role="alert"),
                    html.P(
                        [
                            "Já possui uma conta? ",
                            dcc.Link("Entrar", href="/login", style={"color": "var(--brand)", "fontWeight": "600"}),
                        ],
                        className="t-micro",
                        style={"marginTop": "20px", "textAlign": "center"},
                    ),
                ],
                className="auth__card auth__card--wide",
            ),
            className="auth__main",
        ),
    ],
    className="auth",
)


@callback(
    Output("register-feedback", "children"),
    Output("register-feedback", "className"),
    Output("register-redirect", "href"),
    Input("register-submit", "n_clicks"),
    State("register-company", "value"),
    State("register-slug", "value"),
    State("register-name", "value"),
    State("register-email", "value"),
    State("register-password", "value"),
    State("register-confirm", "value"),
    prevent_initial_call=True,
)
def _register(_clicks, company, slug, name, email, password, confirmation):
    if os.getenv("PULSE_ALLOW_PUBLIC_REGISTRATION", "false").lower() != "true":
        return "Cadastro público desativado. Solicite acesso ao administrador.", "form-feedback form-feedback--error", "/login"
    if password != confirmation:
        return "As senhas não coincidem.", "form-feedback form-feedback--error", dash.no_update
    try:
        create_tenant(
            name=company,
            slug=slug,
            owner_name=name,
            owner_email=email,
            password=password,
        )
        user = authenticate(email, password)
        sign_in(user)
    except ValueError as exc:
        return str(exc), "form-feedback form-feedback--error", dash.no_update
    return "Conta criada. Preparando seu painel...", "form-feedback form-feedback--success", "/"
