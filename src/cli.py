"""CLI para inicializar o banco e coletar nomeações."""
from __future__ import annotations

import logging
from datetime import date, datetime

import click

from . import db
from .scraper import Filtros, SigeoClient, parse_data, parse_valor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sigeo")


def _d(s: str | None) -> date | None:
    return datetime.strptime(s, "%Y-%m-%d").date() if s else None


@click.group()
def cli():
    """Ferramenta de coleta de nomeações do SIGEO."""


@cli.command("init-db")
def init_db():
    """Cria as tabelas no PostgreSQL."""
    db.init_schema()
    click.echo("Schema criado.")


@cli.command("coletar")
@click.option("--tribunal", help="Sigla do tribunal, ex.: TRT1")
@click.option("--data-ini", help="AAAA-MM-DD")
@click.option("--data-fim", help="AAAA-MM-DD")
@click.option("--nome", help="Nome do nomeado (parcial)")
@click.option("--cpf", help="CPF do nomeado")
@click.option("--tipo", "tipo_funcao", help="Perito, Assistente Técnico, Leiloeiro...")
def coletar(tribunal, data_ini, data_fim, nome, cpf, tipo_funcao):
    """Coleta nomeações filtradas e grava no banco."""
    filtros = Filtros(
        tribunal=tribunal,
        data_ini=_d(data_ini),
        data_fim=_d(data_fim),
        nome=nome,
        cpf=cpf,
        tipo_funcao=tipo_funcao,
    )
    client = SigeoClient()
    client.carregar()
    soup = client.pesquisar(filtros)

    novos = 0
    total = 0
    with db.connect() as conn, conn.cursor() as cur:
        for r in client.linhas(soup):
            total += 1
            trib_sigla = r.get("tribunal") or (tribunal or "DESCONHECIDO")
            trib_id = db.upsert_tribunal(cur, trib_sigla)
            orgao_nome = r.get("órgão julgador") or r.get("orgao julgador") or "N/D"
            orgao_id = db.upsert_orgao(cur, trib_id, orgao_nome)
            nom_id = db.upsert_nomeado(cur, r.get("nome") or "N/D", r.get("cpf"))
            payload = {
                "tribunal_id": trib_id,
                "orgao_julgador_id": orgao_id,
                "nomeado_id": nom_id,
                "processo": r.get("processo"),
                "tipo_funcao": r.get("função") or r.get("funcao") or tipo_funcao,
                "especialidade": r.get("especialidade"),
                "data_nomeacao": parse_data(r.get("data") or r.get("data da nomeação")),
                "situacao": r.get("situação") or r.get("situacao"),
                "valor": parse_valor(r.get("valor")),
                "magistrado": r.get("magistrado"),
                "fonte_url": client.url,
                "raw": r,
            }
            if db.insert_nomeacao(cur, payload):
                novos += 1
        conn.commit()
    click.echo(f"Linhas: {total} | novas: {novos}")


if __name__ == "__main__":
    cli()
