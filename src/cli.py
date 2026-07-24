"""CLI: inicializar o banco, coletar nomeações e buscar por profissional."""
from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta

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
    """Coleta nomeações do SIGEO e grava no banco (com paginação)."""
    total, novos = _coletar_intervalo(
        tribunal, _d(data_ini), _d(data_fim),
        [SITUACOES[s] for s in situacoes] if situacoes
                    else list(SITUACOES.values()),
    )
    click.echo(f"Linhas: {total} | novas: {novos}")


def _coletar_intervalo(tribunal: str, data_ini: date, data_fim: date,
                       situacoes: list[str]) -> tuple[int, int]:
    """Coleta um intervalo, paginando todos os resultados."""
    client = SigeoClient()
    client.carregar()
    f = Filtros(tribunal=tribunal, data_ini=data_ini, data_fim=data_fim,
                situacoes=situacoes)
    soup = client.pesquisar(f)
    total_disponivel = client.total_registros(soup) or 0
    rows = 25
    novos = total = 0
    with db.connect() as conn, conn.cursor() as cur:
        trib_id = db.upsert_tribunal(cur, tribunal)
        first = 0
        while True:
            for r in client.linhas(soup, tribunal_sigla=tribunal):
                total += 1
                uni_id = db.upsert_unidade(cur, trib_id, r["unidade"] or "N/D")
                prof_id = db.upsert_profissional(cur, r["nome"] or "N/D")
                if db.insert_nomeacao(cur, {
                    "processo":        r["processo"],
                    "tribunal_id":     trib_id,
                    "unidade_id":      uni_id,
                    "profissional_id": prof_id,
                    "data_nomeacao":   parse_data(r["data"]),
                    "valor":           parse_valor(r["valor"]),
                    "situacao":        r["situacao"],
                    "fonte_url":       client.url,
                    "raw":             r,
                }):
                    novos += 1
            first += rows
            if first >= total_disponivel:
                break
            soup = client.paginar(first, rows)
        conn.commit()
    log.info("%s %s..%s -> total=%d novas=%d",
             tribunal, data_ini, data_fim, total, novos)
    return total, novos


def _meses(ini: date, fim: date):
    """Itera pares (primeiro_dia, ultimo_dia) de cada mês em [ini, fim]."""
    y, m = ini.year, ini.month
    while (y, m) <= (fim.year, fim.month):
        first = date(y, m, 1)
        last = date(y, m, calendar.monthrange(y, m)[1])
        yield max(first, ini), min(last, fim)
        m += 1
        if m == 13:
            m, y = 1, y + 1


@cli.command("backfill")
@click.option("--data-ini", default="2015-01-01", show_default=True,
              help="Data inicial da varredura histórica (AAAA-MM-DD)")
@click.option("--data-fim", default=None,
              help="Data final (padrão: ontem)")
@click.option("--tribunal", "tribunais", multiple=True,
              type=click.Choice(sorted(TRIBUNAIS)),
              help="Restringe a tribunais específicos (padrão: todos)")
def backfill(data_ini, data_fim, tribunais):
    """Baixa toda a base disponível, varrendo mês a mês por tribunal."""
    ini = _d(data_ini)
    fim = _d(data_fim) or (date.today() - timedelta(days=1))
    trts = list(tribunais) if tribunais else sorted(TRIBUNAIS)
    grand_total = grand_novos = 0
    for trt in trts:
        for a, b in _meses(ini, fim):
            try:
                t, n = _coletar_intervalo(trt, a, b, list(SITUACOES.values()))
                grand_total += t
                grand_novos += n
            except Exception as e:
                log.exception("Falha em %s %s..%s: %s", trt, a, b, e)
    click.echo(f"Backfill concluído. Linhas: {grand_total} | novas: {grand_novos}")


@cli.command("coletar-mes-anterior")
@click.option("--tribunal", "tribunais", multiple=True,
              type=click.Choice(sorted(TRIBUNAIS)),
              help="Restringe a tribunais (padrão: todos)")
def coletar_mes_anterior(tribunais):
    """Coleta o mês imediatamente anterior à data de hoje (para cron mensal)."""
    hoje = date.today()
    primeiro_mes_atual = hoje.replace(day=1)
    fim = primeiro_mes_atual - timedelta(days=1)
    ini = fim.replace(day=1)
    trts = list(tribunais) if tribunais else sorted(TRIBUNAIS)
    grand_total = grand_novos = 0
    for trt in trts:
        try:
            t, n = _coletar_intervalo(trt, ini, fim, list(SITUACOES.values()))
            grand_total += t
            grand_novos += n
        except Exception as e:
            log.exception("Falha em %s: %s", trt, e)
    click.echo(f"Mês {ini:%Y-%m}: linhas {grand_total} | novas {grand_novos}")


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
                ON CONFLICT (profissional_id, categoria, profissao,
                             (COALESCE(especialidade, ''))) DO NOTHING
                RETURNING id
                """,
                (pid, categoria, profissao, especialidade),
            )
            if cur.fetchone():
                novas_qual += 1
        conn.commit()
    click.echo(f"Linhas: {total} | profissionais novos: {novos_prof} | qualificações novas: {novas_qual}")


@cli.command("stats")
def stats():
    """Resumo: totais por tribunal, situação, top profissionais e por mês."""
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT profissional_id) FROM nomeacao")
        total, pessoas = cur.fetchone()
        click.echo(f"\n== Totais ==")
        click.echo(f"Nomeações: {total}   Profissionais distintos: {pessoas}\n")

        click.echo("== Por tribunal ==")
        cur.execute("""
            SELECT t.sigla, COUNT(*) FROM nomeacao n
              JOIN tribunal t ON t.id = n.tribunal_id
             GROUP BY t.sigla ORDER BY 2 DESC
        """)
        for sigla, n in cur.fetchall():
            click.echo(f"  {sigla:6s} {n:>8}")

        click.echo("\n== Por situação ==")
        cur.execute("SELECT situacao, COUNT(*) FROM nomeacao GROUP BY 1 ORDER BY 2 DESC")
        for s, n in cur.fetchall():
            click.echo(f"  {s:20s} {n:>8}")

        click.echo("\n== Top 15 profissionais (por nº de nomeações) ==")
        cur.execute("""
            SELECT p.nome, p.profissao, COUNT(*) FROM nomeacao n
              JOIN profissional p ON p.id = n.profissional_id
             GROUP BY p.nome, p.profissao ORDER BY 3 DESC LIMIT 15
        """)
        for nome, prof, n in cur.fetchall():
            click.echo(f"  {n:>5}  {nome[:45]:45s} {prof or ''}")

        click.echo("\n== Por mês (últimos 12) ==")
        cur.execute("""
            SELECT to_char(data_nomeacao, 'YYYY-MM'), COUNT(*) FROM nomeacao
             WHERE data_nomeacao IS NOT NULL
             GROUP BY 1 ORDER BY 1 DESC LIMIT 12
        """)
        for mes, n in cur.fetchall():
            click.echo(f"  {mes}  {n:>8}")


@cli.command("exportar")
@click.argument("saida", type=click.Path(dir_okay=False))
@click.option("--tribunal", help="Filtra por sigla, ex.: TRT2")
@click.option("--data-ini", help="AAAA-MM-DD")
@click.option("--data-fim", help="AAAA-MM-DD")
@click.option("--nome", help="Trecho do nome do profissional")
@click.option("--profissao", help="Trecho da profissão")
def exportar(saida, tribunal, data_ini, data_fim, nome, profissao):
    """Exporta as nomeações filtradas para um CSV (abre no Excel)."""
    import csv as _csv
    clauses, params = [], []
    if tribunal:  clauses.append("t.sigla = %s"); params.append(tribunal)
    if data_ini:  clauses.append("n.data_nomeacao >= %s"); params.append(_d(data_ini))
    if data_fim:  clauses.append("n.data_nomeacao <= %s"); params.append(_d(data_fim))
    if nome:      clauses.append("lower(p.nome) LIKE %s"); params.append(f"%{nome.lower()}%")
    if profissao: clauses.append("lower(p.profissao) LIKE %s"); params.append(f"%{profissao.lower()}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT n.data_nomeacao, t.sigla, u.nome, p.nome, p.profissao,
               n.processo, n.valor, n.situacao
          FROM nomeacao n
          JOIN tribunal t     ON t.id = n.tribunal_id
          JOIN unidade u      ON u.id = n.unidade_id
          JOIN profissional p ON p.id = n.profissional_id
          {where}
         ORDER BY n.data_nomeacao DESC
    """
    with db.connect() as conn, conn.cursor() as cur, \
         open(saida, "w", newline="", encoding="utf-8-sig") as fh:
        cur.execute(sql, params)
        w = _csv.writer(fh, delimiter=";")
        w.writerow(["Data", "Tribunal", "Unidade", "Nome", "Profissão",
                    "Processo", "Valor", "Situação"])
        n = 0
        for row in cur:
            w.writerow(row)
            n += 1
    click.echo(f"Exportadas {n} linhas para {saida}")


@cli.command("web")
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=5001, type=int)
def web(host, port):
    """Sobe a interface web no navegador (http://127.0.0.1:5001)."""
    from .web import main as web_main
    click.echo(f"Abra http://{host}:{port} no navegador")
    web_main(host=host, port=port)


if __name__ == "__main__":
    cli()
