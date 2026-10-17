"""Cadastro de contas extras, frentes e planilhas de leads de um cliente.

O /admin vincula uma conta Meta e uma Google por cliente. Este comando cobre
o que ainda não tem tela: mais de uma conta por plataforma, o rótulo de
frente de cada conta e as abas de planilha com os leads das LPs.

Exemplos:
    python manage_sources.py conta --cliente acme --plataforma meta \\
        --conta 1234567890123456 --frente Franquias
    python manage_sources.py planilha --cliente acme --planilha <id> \\
        --aba "LP Principal" --lp "LP Principal" --frente Assessoria
    python manage_sources.py listar --cliente acme
    python manage_sources.py sincronizar --cliente acme --dias 90
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from core.data import clear_cache
from core.leads import sync_leads
from core.storage import (
    get_tenant_by_slug,
    init_db,
    list_lead_sources,
    set_lead_source,
    set_tenant_media_account,
    tenant_media_accounts,
)
from core.sync import sync_platform


def _tenant(slug: str) -> dict:
    tenant = get_tenant_by_slug(slug)
    if not tenant:
        raise SystemExit(f"Cliente '{slug}' não encontrado. Crie-o antes em /admin.")
    return tenant


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    account = sub.add_parser("conta", help="Vincula uma conta (principal ou extra) e rotula a frente")
    account.add_argument("--cliente", required=True)
    account.add_argument("--plataforma", choices=("meta", "google"), required=True)
    account.add_argument("--conta", required=True)
    account.add_argument("--frente")

    sheet = sub.add_parser("planilha", help="Cadastra uma aba de planilha como fonte de leads")
    sheet.add_argument("--cliente", required=True)
    sheet.add_argument("--planilha", required=True, help="ID da planilha Google")
    sheet.add_argument("--aba", required=True)
    sheet.add_argument("--lp", required=True, help="Nome da LP exibido no painel")
    sheet.add_argument("--frente")

    show = sub.add_parser("listar", help="Mostra contas, frentes e planilhas do cliente")
    show.add_argument("--cliente", required=True)

    run = sub.add_parser("sincronizar", help="Busca agora mídia e leads do cliente")
    run.add_argument("--cliente", required=True)
    run.add_argument("--dias", type=int, default=30)

    args = parser.parse_args()
    init_db()
    tenant = _tenant(args.cliente)

    if args.command == "conta":
        set_tenant_media_account(tenant["id"], args.plataforma, args.conta, args.frente)
    elif args.command == "planilha":
        set_lead_source(tenant["id"], args.planilha, args.aba, args.lp, args.frente)
    elif args.command == "sincronizar":
        end = date.today()
        start = end - timedelta(days=max(1, args.dias) - 1)
        for platform in ("meta", "google"):
            try:
                print(f"{platform}: {sync_platform(tenant, platform, start, end)} linhas ({start} a {end})")
            except Exception as exc:
                print(f"{platform}: ERRO - {type(exc).__name__}: {exc}", file=sys.stderr)
        try:
            print(f"leads: {sync_leads(tenant)} linhas")
        except Exception as exc:
            print(f"leads: ERRO - {type(exc).__name__}: {exc}", file=sys.stderr)
        clear_cache()

    for item in tenant_media_accounts(_tenant(args.cliente)):
        print(f"  conta  {item['platform']:<6} {item['account_id']:<22} frente={item['frente'] or '—'}")
    for source in list_lead_sources(tenant["id"]):
        print(f"  leads  {source['lp']:<22} aba={source['tab']!r} frente={source['frente'] or '—'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(2)
