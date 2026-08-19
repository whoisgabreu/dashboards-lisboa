"""
Aceite de convite: a pessoa convidada define a própria senha.

O administrador nunca inventa nem transmite a senha de ninguém. Ele gera um
link, manda pelo canal que preferir, e quem recebe escolhe a senha na hora de
entrar. Senha provisória enviada por mensagem é a que vaza e nunca é trocada.

A tela já vem com a marca do cliente que convidou — o token identifica o
tenant antes de existir sessão.
"""

from __future__ import annotations

import dash
from dash import Input, Output, State, callback, dcc, html
from flask import has_request_context, request

from core.auth import sign_in
from core.storage import ROLE_LABELS, accept_invite, authenticate, get_invite
from ui.icons import icon
from ui.primitives import card, field, logo, text_input

dash.register_page(__name__, path="/convite", name="Convite", title="Convite")


STATE_MESSAGES = {
    "expired": (
        "Este convite expirou",
        "Convites valem por 7 dias. Peça um novo link para quem administra o painel.",
    ),
    "accepted": (
        "Este convite já foi usado",
        "O acesso correspondente já existe. Entre com o seu e-mail e senha.",
    ),
    "inactive": (
        "Acesso suspenso",
        "O ambiente deste cliente está inativo no momento. Fale com o administrador.",
    ),
    "missing": (
        "Convite não encontrado",
        "O link pode ter sido digitado incompleto. Confira o endereço recebido.",
    ),
}


def _notice(state: str):
    title, description = STATE_MESSAGES[state]
    return card(
        [
            html.Div(logo(), style={"marginBottom": "22px"}),
            html.Div(icon("triangle-alert", 22), className="state__icon", style={"margin": "0 0 14px"}),
            html.H2(title, className="t-page"),
            html.P(description, className="t-micro", style={"marginTop": "8px", "lineHeight": "1.6"}),
            dcc.Link(
                [html.Span("Ir para o login"), icon("arrow-right", 19)],
                href="/login",
                className="btn btn--primary btn--lg btn--block",
                style={"marginTop": "22px"},
            ),
        ],
        className="auth__card",
    )


def _form(invite: dict):
    role_label = ROLE_LABELS.get(invite["role"], "Acesso")
    return card(
        [
            html.Div(logo(), style={"marginBottom": "22px"}),
            html.H2("Criar seu acesso", className="t-page"),
            html.P(
                [
                    "Você foi convidado para o painel de ",
                    html.Strong(invite["tenant_name"]),
                    f" como {role_label.lower()}.",
                ],
                className="t-micro",
                style={"marginTop": "8px", "marginBottom": "22px", "lineHeight": "1.6"},
            ),

            field("Seu nome", text_input("Nome completo", "user", id="invite-name", value=invite["name"])),
            # O e-mail vem travado: é ele que o convite autoriza. Editável,
            # viraria um jeito de criar acesso para outra pessoa.
            field(
                "E-mail de acesso",
                text_input("", "mail", "email", id="invite-email", value=invite["email"], disabled=True),
                hint="Definido pelo convite. Use este e-mail para entrar.",
                className="form-space",
            ),
            html.Div(
                [
                    field("Senha", text_input("Mínimo de 8 caracteres", "lock", "password", id="invite-password")),
                    field("Confirmar senha", text_input("Repita a senha", "lock", "password", id="invite-confirm")),
                ],
                className="form-grid form-grid--2 form-space",
            ),

            html.Button(
                [html.Span("Criar acesso e entrar"), icon("arrow-right", 19)],
                id="invite-submit",
                n_clicks=0,
                className="btn btn--primary btn--lg btn--block",
                style={"marginTop": "22px"},
            ),
            html.Div(id="invite-feedback", className="form-feedback", role="alert"),
        ],
        className="auth__card",
    )


def layout(**_kwargs):
    token = request.args.get("token") if has_request_context() else None
    invite = get_invite(token)
    state = invite["state"] if invite else "missing"

    return html.Div(
        [
            dcc.Location(id="invite-redirect", refresh=True),
            dcc.Store(id="invite-token", data=token),
            html.Aside(
                [
                    html.Div(className="auth__bg"),
                    html.Div(logo(), className="auth__aside-inner"),
                    html.Div(
                        [
                            html.Span("ACESSO AO PAINEL", className="eyebrow"),
                            html.H1(
                                "A performance das campanhas, aberta para o seu time.",
                                className="auth__headline",
                            ),
                            html.P(
                                "Meta Ads e Google Ads no mesmo lugar, com investimento, "
                                "leads e custo por lead atualizados.",
                                className="auth__lede",
                            ),
                        ],
                        className="auth__aside-inner",
                    ),
                    html.Div(
                        "Seu acesso é individual — cada pessoa entra com o próprio e-mail.",
                        className="auth__proof-label",
                        style={"position": "relative"},
                    ),
                ],
                className="auth__aside",
            ),
            html.Main(
                _form(invite) if state == "pending" else _notice(state),
                className="auth__main",
            ),
        ],
        className="auth",
    )


@callback(
    Output("invite-feedback", "children"),
    Output("invite-feedback", "className"),
    Output("invite-redirect", "href"),
    Input("invite-submit", "n_clicks"),
    State("invite-token", "data"),
    State("invite-name", "value"),
    State("invite-password", "value"),
    State("invite-confirm", "value"),
    prevent_initial_call=True,
)
def _accept(_clicks, token, name, password, confirmation):
    if password != confirmation:
        return "As senhas não coincidem.", "form-feedback form-feedback--error", dash.no_update

    try:
        user = accept_invite(token, password=password, name=name)
        # Entra direto: pedir para digitar de novo o que acabou de ser
        # definido é um passo sem função.
        signed = authenticate(user["email"], password)
        if signed:
            sign_in(signed)
    except ValueError as exc:
        return str(exc), "form-feedback form-feedback--error", dash.no_update

    return "Acesso criado. Abrindo seu painel...", "form-feedback form-feedback--success", "/"
