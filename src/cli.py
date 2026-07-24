"""CLI: inicializar o banco, coletar nomeações e buscar por profissional."""
from __future__ import annotations

import logging
from datetime import date, datetime

import click

from . import db
from .scraper import (
    Filtros, SITUACOES, SigeoClient, TRIBUNAIS,
    parse_data, parse_valor,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sigeo")


def _d(s: str | None) -> date | None:
    return datetime.strptime(s, "%Y-%m-%d").date() if s else None


@click.group()
def cli():
    """Ferramenta de coleta e consulta de nomeações do SIGEO."""


@cli.command("init-db")
def init_db():
    """Cria as tabelas no PostgreSQL."""
    db.init_schema()
    click.echo("Schema criado.")


@cli.command("coletar")
@click.option("--tribunal", type=click.Choice(sorted(TRIBUNAIS)), required=True,
              help="Sigla do tribunal, ex.: TRT1")
@click.option("--data-ini", required=True, help="AAAA-MM-DD")
@click.option("--data-fim", required=True, help="AAAA-MM-DD")
@click.option("--situacao", "situacoes", multiple=True,
              type=click.Choice(list(SITUACOES)),
              help="Uma ou mais situações (padrão: todas)")
def coletar(tribunal, data_ini, data_fim, situacoes):
    """Coleta nomeações do SIGEO e grava no banco."""
    f = Filtros(
        tribunal=tribunal,
        data_ini=_d(data_ini),
        data_fim=_d(data_fim),
        situacoes=[SITUACOES[s] for s in situacoes] if situacoes
                  else list(SITUACOES.values()),
    )
    client = SigeoClient()
    client.carregar()
    soup = client.pesquisar(f)

    novos = total = 0
    with db.connect() as conn, conn.cursor() as cur:
        trib_id = db.upsert_tribunal(cur, tribunal)
        for r in client.linhas(soup, tribunal_sigla=tribunal):
            total += 1
            uni_id = db.upsert_unidade(cur, trib_id, r["unidade"] or "N/D")
            prof_id = db.upsert_profissional(cur, r["nome"] or "N/D")
            payload = {
                "processo":        r["processo"],
                "tribunal_id":     trib_id,
                "unidade_id":      uni_id,
                "profissional_id": prof_id,
                "data_nomeacao":   parse_data(r["data"]),
                "valor":           parse_valor(r["valor"]),
                "situacao":        r["situacao"],
                "fonte_url":       client.url,
                "raw":             r,
            }
            if db.insert_nomeacao(cur, payload):
                novos += 1
        conn.commit()
    click.echo(f"Linhas: {total} | novas: {novos}")


@cli.command("buscar")
@click.option("--nome", help="Trecho do nome do profissional (case-insensitive)")
@click.option("--profissao", help="Trecho da profissão (case-insensitive)")
@click.option("--tribunal", help="Sigla do tribunal")
@click.option("--situacao", help="ex.: ACEITA")
@click.option("--limite", type=int, default=50)
def buscar(nome, profissao, tribunal, situacao, limite):
    """Consulta local, útil já que o SIGEO não filtra por nome."""
    clauses, params = [], []
    if nome:
        clauses.append("lower(p.nome) LIKE %s"); params.append(f"%{nome.lower()}%")
    if profissao:
        clauses.append("lower(p.profissao) LIKE %s"); params.append(f"%{profissao.lower()}%")
    if tribunal:
        clauses.append("t.sigla = %s"); params.append(tribunal)
    if situacao:
        clauses.append("n.situacao ILIKE %s"); params.append(situacao)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT n.data_nomeacao, t.sigla, u.nome AS unidade,
               p.nome, p.profissao, n.processo, n.valor, n.situacao
          FROM nomeacao n
          JOIN tribunal t ON t.id = n.tribunal_id
          JOIN unidade u  ON u.id = n.unidade_id
          JOIN profissional p ON p.id = n.profissional_id
          {where}
         ORDER BY n.data_nomeacao DESC
         LIMIT %s
    """
    params.append(limite)
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        for row in cur.fetchall():
            click.echo(" | ".join("" if v is None else str(v) for v in row))


@cli.command("set-profissao")
@click.option("--nome", required=True, help="Nome exato ou trecho (LIKE) do profissional")
@click.option("--profissao", required=True, help="Profissão a atribuir")
@click.option("--exato/--like", default=False, help="Casamento exato do nome (padrão: LIKE)")
def set_profissao(nome, profissao, exato):
    """Preenche/atualiza a profissão de um ou vários profissionais."""
    with db.connect() as conn, conn.cursor() as cur:
        if exato:
            cur.execute(
                "UPDATE profissional SET profissao = %s WHERE nome = %s",
                (profissao, nome),
            )
        else:
            cur.execute(
                "UPDATE profissional SET profissao = %s WHERE lower(nome) LIKE %s",
                (profissao, f"%{nome.lower()}%"),
            )
        conn.commit()
        click.echo(f"Atualizados: {cur.rowcount}")


@cli.command("import-profissoes")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
def import_profissoes(csv_path):
    """Importa profissões de um CSV com cabeçalho 'nome,profissao'."""
    import csv
    ok = 0
    with open(csv_path, newline="", encoding="utf-8") as fh, \
         db.connect() as conn, conn.cursor() as cur:
        for r in csv.DictReader(fh):
            cur.execute(
                """
                INSERT INTO profissional (nome, profissao) VALUES (%s, %s)
                ON CONFLICT (nome) DO UPDATE SET profissao = EXCLUDED.profissao
                """,
                (r["nome"].strip(), (r.get("profissao") or "").strip() or None),
            )
            ok += 1
        conn.commit()
    click.echo(f"Linhas processadas: {ok}")


@cli.command("import-peritos")
@click.argument("tsv_path", type=click.Path(exists=True, dir_okay=False))
def import_peritos(tsv_path):
    """Importa o cadastro CNPTJ (TSV: Nome<TAB>Categoria<TAB>Profissão<TAB>Especialidade).

    Aceita cabeçalho na primeira linha (é ignorado se começar com 'Nome').
    Uma pessoa pode ter várias linhas — cada uma vira uma qualificação.
    """
    novos_prof = novas_qual = total = 0
    with open(tsv_path, encoding="utf-8") as fh, \
         db.connect() as conn, conn.cursor() as cur:
        for i, line in enumerate(fh):
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            if i == 0 and parts[0].strip().lower() == "nome":
                continue
            nome = parts[0].strip()
            categoria = parts[1].strip()
            profissao = parts[2].strip()
            especialidade = (parts[3].strip() if len(parts) > 3 else "") or None
            if not (nome and categoria and profissao):
                continue
            total += 1
            cur.execute(
                """
                INSERT INTO profissional (nome, profissao) VALUES (%s, %s)
                ON CONFLICT (nome) DO UPDATE SET profissao =
                    COALESCE(profissional.profissao, EXCLUDED.profissao)
                RETURNING id, (xmax = 0) AS inserted
                """,
                (nome, profissao),
            )
            pid, inserted = cur.fetchone()
            if inserted:
                novos_prof += 1
            cur.execute(
                """
                INSERT INTO qualificacao
                    (profissional_id, categoria, profissao, especialidade)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                (pid, categoria, profissao, especialidade),
            )
            if cur.fetchone():
                novas_qual += 1
        conn.commit()
    click.echo(f"Linhas: {total} | profissionais novos: {novos_prof} | qualificações novas: {novas_qual}")


if __name__ == "__main__":
    cli()
