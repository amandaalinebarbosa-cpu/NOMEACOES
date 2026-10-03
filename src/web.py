"""Interface web para navegar nas nomeações SIGEO.

Rodar: `python -m src.cli web`  → abre http://127.0.0.1:5001
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime

from flask import Flask, render_template_string, request, Response

from . import db

app = Flask(__name__)


TPL = """
<!doctype html>
<html lang="pt-br"><head>
<meta charset="utf-8"><title>Peritus Dominus — Nomeações SIGEO</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --pd-navy:  #1E3A2A;
    --pd-navy2: #142821;
    --pd-gold:  #B8941F;
    --pd-green: #16A34A;
    --pd-cream: #F5F0E6;
    --pd-ink:   #2C2C2C;
    --pd-mute:  #8B8477;
  }
  html, body { background: var(--pd-cream); color: var(--pd-ink); }
  body { font-family: 'Inter', system-ui, sans-serif; }
  h1, h2, h3, h4, h5, .brand { font-family: 'Cormorant Garamond', 'Times New Roman', serif; letter-spacing: .5px; }

  .pd-header {
    background: linear-gradient(135deg, var(--pd-navy) 0%, var(--pd-navy2) 100%);
    color: #fff; padding: 22px 28px; margin-bottom: 24px;
    display: flex; justify-content: space-between; align-items: center;
    border-bottom: 3px solid var(--pd-gold);
  }
  .brand { font-size: 1.9rem; font-weight: 700; display: flex; align-items: center; gap: 12px; }
  .brand .seal {
    width: 42px; height: 42px; border: 2px solid var(--pd-gold);
    display: inline-flex; align-items: center; justify-content: center;
    border-radius: 50%; color: var(--pd-gold); font-weight: 700; font-size: 1.1rem;
  }
  .brand small { color: var(--pd-gold); font-size: .75rem; letter-spacing: 2px; text-transform: uppercase; font-family: 'Inter', sans-serif; font-weight: 500; display: block; margin-top: 2px; }

  .pd-nav a { color: #fff; text-decoration: none; margin-left: 20px; font-size: .9rem; font-weight: 500; opacity: .85; }
  .pd-nav a:hover { opacity: 1; color: var(--pd-gold); }
  .pd-nav .btn-print { background: var(--pd-gold); color: var(--pd-navy); border: 0; padding: 8px 18px; border-radius: 4px; font-weight: 600; }
  .pd-nav .btn-print:hover { background: #d4ab2d; color: var(--pd-navy); }

  .container-fluid { padding: 0 28px 40px; }

  .stats { display: flex; gap: 16px; margin-bottom: 22px; flex-wrap: wrap; }
  .stat-card {
    background: #fff; padding: 16px 22px; border-radius: 10px;
    border-top: 3px solid var(--pd-gold); min-width: 200px;
    box-shadow: 0 1px 4px rgba(30,58,42,.08);
  }
  .stat-num { font-family: 'Cormorant Garamond', serif; font-size: 2rem; font-weight: 700; color: var(--pd-navy); line-height: 1.1; }
  .stat-card > div:last-child { color: var(--pd-mute); font-size: .72rem; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600; margin-top: 4px; }

  .filters {
    background: #fff; padding: 20px 22px; border-radius: 10px; margin-bottom: 22px;
    box-shadow: 0 1px 4px rgba(30,58,42,.08); border-left: 3px solid var(--pd-gold);
  }
  .filters .form-label { color: var(--pd-mute); font-size: .72rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; margin-bottom: 4px; }
  .filters .form-control, .filters .form-select { border-color: #d8d2c2; font-size: .9rem; }
  .filters .form-control:focus, .filters .form-select:focus { border-color: var(--pd-gold); box-shadow: 0 0 0 .2rem rgba(184,148,31,.2); }

  .btn-pd { background: var(--pd-navy); color: #fff; border: 0; font-weight: 600; padding: 8px 20px; border-radius: 4px; letter-spacing: .5px; }
  .btn-pd:hover { background: var(--pd-navy2); color: var(--pd-gold); }
  .btn-outline-pd { background: #fff; color: var(--pd-navy); border: 1px solid var(--pd-navy); font-weight: 500; padding: 7px 16px; border-radius: 4px; }
  .btn-outline-pd:hover { background: var(--pd-navy); color: #fff; }
  .btn-gold { background: var(--pd-gold); color: var(--pd-navy); border: 0; font-weight: 600; padding: 8px 16px; border-radius: 4px; }
  .btn-gold:hover { background: #d4ab2d; color: var(--pd-navy); }
  .btn-green { background: var(--pd-green); color: #fff; border: 0; font-weight: 600; padding: 8px 16px; border-radius: 4px; }
  .btn-green:hover { background: #0f7a37; color: #fff; }

  .form-check-input:checked { background-color: var(--pd-gold); border-color: var(--pd-gold); }

  table.dataTable { font-size: .88rem; background: #fff; border-radius: 8px; overflow: hidden; }
  table.dataTable thead th {
    position: sticky; top: 0; background: var(--pd-navy); color: #fff;
    border-bottom: 2px solid var(--pd-gold); font-weight: 600;
    text-transform: uppercase; font-size: .72rem; letter-spacing: 1px; padding: 10px 12px;
  }
  table.dataTable tbody tr:nth-of-type(even) { background: #fafaf5; }
  table.dataTable tbody tr:hover { background: #f0ead9; }
  table.dataTable td { padding: 8px 12px; border-color: #e9e4d6; }
</style>
</head><body>

<header class="pd-header">
  <div class="brand">
    <span class="seal">PD</span>
    <div>Peritus Dominus
      <small>Nomeações SIGEO · Justiça do Trabalho</small>
    </div>
  </div>
  <nav class="pd-nav">
    <a href="/?{{ query_string }}">Tabela</a>
    <a href="/dashboard?{{ query_string }}">Dashboard</a>
    <a href="/export?{{ query_string }}">CSV</a>
    <a href="/export/xlsx?{{ query_string }}">📊 Excel</a>
    <a href="/relatorio?{{ query_string }}" class="btn-print">📄 Gerar Relatório PDF</a>
  </nav>
</header>

<div class="container-fluid">

  <div class="stats">
    <div class="stat-card"><div class="stat-num">{{ "{:,}".format(total_geral).replace(",", ".") }}</div><div>Total no banco</div></div>
    <div class="stat-card"><div class="stat-num">{{ "{:,}".format(total_filtrado).replace(",", ".") }}</div><div>Com filtros atuais</div></div>
    <div class="stat-card"><div class="stat-num">{{ "{:,}".format(total_profissionais).replace(",", ".") }}</div><div>Profissionais distintos</div></div>
  </div>

  <form class="filters" method="get">
    <div class="row g-2">
      <div class="col-md-2">
        <label class="form-label">Tribunal</label>
        <select name="tribunal" class="form-select">
          <option value="">(todos)</option>
          {% for t in tribunais %}
          <option value="{{ t }}" {% if t==filtros.tribunal %}selected{% endif %}>{{ t }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-md-3">
        <label class="form-label">Unidade (vara)</label>
        <input type="text" name="unidade" class="form-control" value="{{ filtros.unidade or '' }}" placeholder="ex.: 12ª Vara do Trabalho">
      </div>
      <div class="col-md-2">
        <label class="form-label">Nome do profissional</label>
        <input type="text" name="nome" class="form-control" value="{{ filtros.nome or '' }}" placeholder="ex.: silva">
      </div>
      <div class="col-md-2">
        <label class="form-label">Profissão</label>
        <select name="profissao" class="form-select">
          <option value="">(todas)</option>
          {% for p in profissoes %}
          <option value="{{ p }}" {% if p==filtros.profissao %}selected{% endif %}>{{ p }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-md-1">
        <label class="form-label">Situação</label>
        <select name="situacao" class="form-select">
          <option value="">(todas)</option>
          {% for s in situacoes %}
          <option value="{{ s }}" {% if s==filtros.situacao %}selected{% endif %}>{{ s }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-md-1">
        <label class="form-label">De</label>
        <input type="date" name="data_ini" class="form-control" value="{{ filtros.data_ini or '' }}">
      </div>
      <div class="col-md-1">
        <label class="form-label">Até</label>
        <input type="date" name="data_fim" class="form-control" value="{{ filtros.data_fim or '' }}">
      </div>
    </div>
    <div class="mt-3 d-flex gap-2 align-items-center flex-wrap">
      <button class="btn btn-pd" type="submit">Filtrar</button>
      <a class="btn btn-outline-pd" href="/">Limpar</a>
      <a class="btn btn-green" href="/export?{{ query_string }}">📥 CSV</a>
      <a class="btn btn-gold" href="/export/xlsx?{{ query_string }}">📊 Excel</a>
      <div class="form-check ms-3">
        <input type="hidden" name="validas" value="0">
        <input class="form-check-input" type="checkbox" name="validas" value="1" id="validasChk" {% if filtros.validas == '1' %}checked{% endif %}>
        <label class="form-check-label" for="validasChk">
          Excluir <b>CANCELADA</b>
        </label>
      </div>
    </div>
  </form>

  <p class="text-muted" style="font-size:.85rem;">Mostrando {{ linhas|length }} de {{ "{:,}".format(total_filtrado).replace(",", ".") }} resultados (limite {{ limite }}).</p>

  <div class="table-responsive" style="max-height: 70vh;">
    <table class="table table-striped table-sm dataTable">
      <thead><tr>
        <th>Data</th><th>Tribunal</th><th>Unidade</th><th>Nome</th>
        <th>Profissão</th><th>Processo</th><th>Valor</th><th>Situação</th>
      </tr></thead>
      <tbody>
      {% for r in linhas %}
        <tr>
          <td>{{ r[0].strftime('%d/%m/%Y') if r[0] else '' }}</td>
          <td>{{ r[1] }}</td>
          <td>{{ r[2] }}</td>
          <td>{{ r[3] }}</td>
          <td>{{ r[4] or '' }}</td>
          <td>{{ r[5] or '' }}</td>
          <td>{{ 'R$ %s'|format('{:,.2f}'.format(r[6]).replace(',','X').replace('.',',').replace('X','.')) if r[6] else '' }}</td>
          <td>{{ r[7] or '' }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
</body></html>
"""


def _parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date() if s else None


SITUACOES_INVALIDAS = ["CANCELADA"]  # tudo o resto é "válido"


def _build_query(args):
    clauses, params = [], []
    tribunal = args.get("tribunal") or None
    unidade = args.get("unidade") or None
    nome = args.get("nome") or None
    profissao = args.get("profissao") or None
    situacao = args.get("situacao") or None
    data_ini = args.get("data_ini") or None
    data_fim = args.get("data_fim") or None
    # "válidas" = ACEITA + SERVIÇO PRESTADO. Padrão ligado; usuário desliga
    # marcando "todas" no checkbox (querystring: validas=0).
    # Ausência do parâmetro (primeira visita) = ligado.
    validas = args.get("validas")
    if validas is None:
        validas = "1"
    if tribunal:
        clauses.append("t.sigla = %s"); params.append(tribunal)
    if unidade:
        clauses.append("lower(u.nome) LIKE %s"); params.append(f"%{unidade.lower()}%")
    if nome:
        clauses.append("lower(p.nome) LIKE %s"); params.append(f"%{nome.lower()}%")
    if profissao:
        clauses.append("p.profissao = %s"); params.append(profissao)
    if situacao:
        clauses.append("n.situacao = %s"); params.append(situacao)
    elif validas == "1":
        clauses.append("(n.situacao IS NULL OR n.situacao <> ALL(%s))")
        params.append(SITUACOES_INVALIDAS)
    if data_ini:
        clauses.append("n.data_nomeacao >= %s"); params.append(_parse_date(data_ini))
    if data_fim:
        clauses.append("n.data_nomeacao <= %s"); params.append(_parse_date(data_fim))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    filtros = {"tribunal": tribunal, "unidade": unidade, "nome": nome,
               "profissao": profissao, "situacao": situacao,
               "data_ini": data_ini, "data_fim": data_fim,
               "validas": validas}
    return where, params, filtros


@app.route("/")
def index():
    limite = int(request.args.get("limite", 500))
    where, params, filtros = _build_query(request.args)
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM nomeacao")
        total_geral = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT id) FROM profissional")
        total_profissionais = cur.fetchone()[0]
        cur.execute(f"""
            SELECT COUNT(*) FROM nomeacao n
              JOIN tribunal t     ON t.id = n.tribunal_id
              JOIN unidade u      ON u.id = n.unidade_id
              JOIN profissional p ON p.id = n.profissional_id
            {where}
        """, params)
        total_filtrado = cur.fetchone()[0]
        cur.execute(f"""
            SELECT n.data_nomeacao, t.sigla, u.nome, p.nome, p.profissao,
                   n.processo, n.valor, n.situacao
              FROM nomeacao n
              JOIN tribunal t     ON t.id = n.tribunal_id
              JOIN unidade u      ON u.id = n.unidade_id
              JOIN profissional p ON p.id = n.profissional_id
              {where}
             ORDER BY n.data_nomeacao DESC NULLS LAST
             LIMIT %s
        """, params + [limite])
        linhas = cur.fetchall()
        cur.execute("SELECT sigla FROM tribunal ORDER BY sigla")
        tribunais = [r[0] for r in cur.fetchall()]
        cur.execute("""
            SELECT DISTINCT profissao FROM profissional
             WHERE profissao IS NOT NULL AND profissao <> ''
             ORDER BY profissao
        """)
        profissoes = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT situacao FROM nomeacao WHERE situacao IS NOT NULL ORDER BY situacao")
        situacoes = [r[0] for r in cur.fetchall()]

    return render_template_string(
        TPL, linhas=linhas, filtros=filtros,
        tribunais=tribunais, profissoes=profissoes, situacoes=situacoes,
        total_geral=total_geral, total_filtrado=total_filtrado,
        total_profissionais=total_profissionais,
        limite=limite, query_string=request.query_string.decode(),
    )


@app.route("/export")
def export():
    where, params, _ = _build_query(request.args)
    buf = io.StringIO()
    buf.write("﻿")  # BOM para Excel abrir com acento
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Data", "Tribunal", "Unidade", "Nome", "Profissão",
                "Processo", "Valor", "Situação"])
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(f"""
            SELECT n.data_nomeacao, t.sigla, u.nome, p.nome, p.profissao,
                   n.processo, n.valor, n.situacao
              FROM nomeacao n
              JOIN tribunal t     ON t.id = n.tribunal_id
              JOIN unidade u      ON u.id = n.unidade_id
              JOIN profissional p ON p.id = n.profissional_id
              {where}
             ORDER BY n.data_nomeacao DESC NULLS LAST
        """, params)
        for row in cur:
            w.writerow(row)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition":
                 f"attachment; filename=nomeacoes_{date.today():%Y%m%d}.csv"},
    )


@app.route("/export/xlsx")
def export_xlsx():
    """Exportação em Excel (.xlsx) formatada, com os mesmos filtros."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    where, params, filtros = _build_query(request.args)

    wb = Workbook()
    ws = wb.active
    ws.title = "Nomeações SIGEO"

    # ---- cabeçalho Peritus Dominus ----
    ws.merge_cells("A1:H1")
    c = ws["A1"]
    c.value = "PERITUS DOMINUS — Nomeações SIGEO"
    c.font = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor="1E3A2A")
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:H2")
    c = ws["A2"]
    c.value = f"Relatório emitido em {datetime.now():%d/%m/%Y %H:%M}"
    c.font = Font(size=10, italic=True, color="595959")
    c.alignment = Alignment(horizontal="center")

    # resumo dos filtros aplicados
    partes = []
    if filtros.get("tribunal"): partes.append(f"Tribunal={filtros['tribunal']}")
    if filtros.get("unidade"):  partes.append(f"Unidade={filtros['unidade']}")
    if filtros.get("nome"):     partes.append(f"Perito={filtros['nome']}")
    if filtros.get("profissao"):partes.append(f"Profissão={filtros['profissao']}")
    if filtros.get("data_ini"): partes.append(f"De={filtros['data_ini']}")
    if filtros.get("data_fim"): partes.append(f"Até={filtros['data_fim']}")
    if filtros.get("validas") == "1": partes.append("Excluídas as CANCELADA")
    ws.merge_cells("A3:H3")
    ws["A3"].value = "Filtros: " + (" · ".join(partes) if partes else "nenhum")
    ws["A3"].font = Font(size=9, color="8B8477")

    # ---- cabeçalho da tabela ----
    header_row = 5
    headers = ["Data", "Tribunal", "Unidade", "Nome", "Profissão",
               "Processo", "Valor (R$)", "Situação"]
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=header_row, column=i, value=h)
        c.font = Font(bold=True, color="FFFFFF", size=11)
        c.fill = PatternFill("solid", fgColor="1E3A2A")
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = Border(bottom=Side(style="medium", color="B8941F"))
    ws.row_dimensions[header_row].height = 22

    # ---- dados ----
    thin = Side(style="thin", color="E9E4D6")
    alt_fill = PatternFill("solid", fgColor="FAF8F2")
    r = header_row + 1
    total = 0
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(f"""
            SELECT n.data_nomeacao, t.sigla, u.nome, p.nome, p.profissao,
                   n.processo, n.valor, n.situacao
              FROM nomeacao n
              JOIN tribunal t     ON t.id = n.tribunal_id
              JOIN unidade u      ON u.id = n.unidade_id
              JOIN profissional p ON p.id = n.profissional_id
              {where}
             ORDER BY n.data_nomeacao DESC NULLS LAST
        """, params)
        for row in cur:
            data_v, tribunal_v, unid_v, nome_v, prof_v, proc_v, valor_v, sit_v = row
            cells = [
                (data_v, "dd/mm/yyyy"),
                (tribunal_v, None), (unid_v, None), (nome_v, None),
                (prof_v, None), (proc_v, "@"),
                (valor_v, '"R$ "#,##0.00'),
                (sit_v, None),
            ]
            for col_i, (val, fmt) in enumerate(cells, 1):
                cc = ws.cell(row=r, column=col_i, value=val)
                if fmt: cc.number_format = fmt
                cc.border = Border(left=thin, right=thin, top=thin, bottom=thin)
                if r % 2 == 0: cc.fill = alt_fill
            total += 1
            r += 1

    # ---- larguras ----
    widths = [12, 10, 48, 36, 24, 24, 14, 20]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    ws.auto_filter.ref = f"A{header_row}:H{r-1 if r > header_row + 1 else header_row}"

    # ---- rodapé com total ----
    foot_row = r + 1
    ws.merge_cells(start_row=foot_row, start_column=1, end_row=foot_row, end_column=5)
    ws.cell(row=foot_row, column=1,
            value=f"Total: {total:,} nomeações".replace(",", ".")
            ).font = Font(bold=True, color="1E3A2A")
    ws.cell(row=foot_row, column=1).alignment = Alignment(horizontal="right")

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":
                 f"attachment; filename=nomeacoes_{date.today():%Y%m%d}.xlsx"},
    )


DASH_TPL = """
<!doctype html>
<html lang="pt-br"><head>
<meta charset="utf-8"><title>Peritus Dominus — Nomeações SIGEO</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
  :root {
    --pd-navy:  #1E3A2A;   /* verde escuro Peritus Dominus */
    --pd-navy2: #142821;   /* verde ainda mais escuro */
    --pd-gold:  #B8941F;   /* dourado DOMINUS */
    --pd-green: #16A34A;   /* verde CTA */
    --pd-cream: #F5F0E6;   /* bege fundo */
    --pd-ink:   #2C2C2C;
    --pd-mute:  #8B8477;
  }
  html, body { background: var(--pd-cream); color: var(--pd-ink); }
  body { font-family: 'Inter', system-ui, sans-serif; }
  h1, h2, h3, h4, h5, .brand { font-family: 'Cormorant Garamond', 'Times New Roman', serif; letter-spacing: .5px; }

  .pd-header {
    background: linear-gradient(135deg, var(--pd-navy) 0%, var(--pd-navy2) 100%);
    color: #fff; padding: 22px 28px; margin-bottom: 24px;
    display: flex; justify-content: space-between; align-items: center;
    border-bottom: 3px solid var(--pd-gold);
  }
  .brand { font-size: 1.9rem; font-weight: 700; display: flex; align-items: center; gap: 12px; }
  .brand .seal {
    width: 42px; height: 42px; border: 2px solid var(--pd-gold);
    display: inline-flex; align-items: center; justify-content: center;
    border-radius: 50%; color: var(--pd-gold); font-weight: 700; font-size: 1.1rem;
  }
  .brand small { color: var(--pd-gold); font-size: .75rem; letter-spacing: 2px; text-transform: uppercase; font-family: 'Inter', sans-serif; font-weight: 500; display: block; margin-top: 2px; }

  .pd-nav a { color: #fff; text-decoration: none; margin-left: 20px; font-size: .9rem; font-weight: 500; opacity: .85; }
  .pd-nav a:hover { opacity: 1; color: var(--pd-gold); }
  .pd-nav .btn-print { background: var(--pd-gold); color: var(--pd-navy); border: 0; padding: 8px 18px; border-radius: 4px; font-weight: 600; }
  .pd-nav .btn-print:hover { background: #e0c278; color: var(--pd-navy); }

  .container-fluid { padding: 0 28px 40px; }

  .kpi {
    background: #fff; border-radius: 10px; padding: 20px 22px;
    border-top: 3px solid var(--pd-gold);
    box-shadow: 0 1px 4px rgba(26,40,71,.08);
  }
  .kpi .num { font-family: 'Cormorant Garamond', serif; font-size: 2.4rem; font-weight: 700; color: var(--pd-navy); line-height: 1.1; }
  .kpi .lbl { color: var(--pd-mute); font-size: .75rem; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600; margin-bottom: 6px; }

  .card-chart {
    background: #fff; border-radius: 10px; padding: 22px;
    box-shadow: 0 1px 4px rgba(26,40,71,.08); height: 100%;
  }
  .card-chart h5 {
    margin-bottom: 16px; color: var(--pd-navy); font-weight: 700;
    font-size: 1.25rem; border-bottom: 1px solid #e9e4d6; padding-bottom: 10px;
  }
  canvas { max-height: 350px; }

  .filters {
    background: #fff; padding: 20px 22px; border-radius: 10px; margin-bottom: 22px;
    box-shadow: 0 1px 4px rgba(26,40,71,.08); border-left: 3px solid var(--pd-gold);
  }
  .filters .form-label { color: var(--pd-mute); font-size: .72rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; margin-bottom: 4px; }
  .filters .form-control, .filters .form-select { border-color: #d8d2c2; font-size: .9rem; }
  .filters .form-control:focus, .filters .form-select:focus { border-color: var(--pd-gold); box-shadow: 0 0 0 .2rem rgba(201,169,97,.2); }

  .btn-pd {
    background: var(--pd-navy); color: #fff; border: 0; font-weight: 600;
    padding: 8px 20px; border-radius: 4px; letter-spacing: .5px;
  }
  .btn-pd:hover { background: var(--pd-navy2); color: var(--pd-gold); }
  .btn-outline-pd {
    background: #fff; color: var(--pd-navy); border: 1px solid var(--pd-navy);
    font-weight: 500; padding: 7px 16px; border-radius: 4px;
  }
  .btn-outline-pd:hover { background: var(--pd-navy); color: #fff; }

  .form-check-input:checked { background-color: var(--pd-gold); border-color: var(--pd-gold); }

  .section-title { color: var(--pd-navy); font-size: 1rem; text-transform: uppercase; letter-spacing: 2px; font-weight: 600; font-family: 'Inter', sans-serif; margin: 28px 0 14px; padding-left: 10px; border-left: 3px solid var(--pd-gold); }
</style>
</head><body>

<header class="pd-header">
  <div class="brand">
    <span class="seal">PD</span>
    <div>Peritus Dominus
      <small>Nomeações SIGEO · Justiça do Trabalho</small>
    </div>
  </div>
  <nav class="pd-nav">
    <a href="/?{{ query_string }}">Tabela</a>
    <a href="/dashboard?{{ query_string }}">Dashboard</a>
    <a href="/export?{{ query_string }}">CSV</a>
    <a href="/export/xlsx?{{ query_string }}">📊 Excel</a>
    <a href="/relatorio?{{ query_string }}" class="btn-print">📄 Gerar Relatório PDF</a>
  </nav>
</header>

<div class="container-fluid">

  <form class="filters" method="get">
    <div class="row g-2">
      <div class="col-md-2">
        <label class="form-label">Tribunal</label>
        <select name="tribunal" class="form-select">
          <option value="">(todos)</option>
          {% for t in tribunais %}
          <option value="{{ t }}" {% if t==filtros.tribunal %}selected{% endif %}>{{ t }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-md-3">
        <label class="form-label">Unidade (vara)</label>
        <input type="text" name="unidade" class="form-control" value="{{ filtros.unidade or '' }}" placeholder="ex.: 12ª Vara">
      </div>
      <div class="col-md-2">
        <label class="form-label">Nome do perito</label>
        <input type="text" name="nome" class="form-control" value="{{ filtros.nome or '' }}" placeholder="ex.: silva">
      </div>
      <div class="col-md-2">
        <label class="form-label">Profissão</label>
        <select name="profissao" class="form-select">
          <option value="">(todas)</option>
          {% for p in profissoes %}
          <option value="{{ p }}" {% if p==filtros.profissao %}selected{% endif %}>{{ p }}</option>
          {% endfor %}
        </select>
      </div>
      <div class="col-md-1">
        <label class="form-label">De</label>
        <input type="date" name="data_ini" class="form-control" value="{{ filtros.data_ini or '' }}">
      </div>
      <div class="col-md-1">
        <label class="form-label">Até</label>
        <input type="date" name="data_fim" class="form-control" value="{{ filtros.data_fim or '' }}">
      </div>
      <div class="col-md-1 d-flex align-items-end gap-2">
        <button class="btn btn-pd flex-grow-1" type="submit">Filtrar</button>
      </div>
    </div>
    <div class="mt-3 d-flex gap-3 align-items-center">
      <a class="btn btn-sm btn-outline-pd" href="/dashboard">Limpar filtros</a>
      <div class="form-check">
        <input type="hidden" name="validas" value="0">
        <input class="form-check-input" type="checkbox" name="validas" value="1" id="dashValidasChk" {% if filtros.validas == '1' %}checked{% endif %}>
        <label class="form-check-label" for="dashValidasChk">
          Excluir <b>CANCELADA</b>
        </label>
      </div>
    </div>
  </form>

  <div class="row g-3 mb-4">
    <div class="col-md-3"><div class="kpi"><div class="lbl">Nomeações</div><div class="num">{{ "{:,}".format(kpis.total).replace(",",".") }}</div></div></div>
    <div class="col-md-3"><div class="kpi"><div class="lbl">Profissionais</div><div class="num">{{ "{:,}".format(kpis.pessoas).replace(",",".") }}</div></div></div>
    <div class="col-md-3"><div class="kpi"><div class="lbl">Tribunais</div><div class="num">{{ kpis.tribunais }}</div></div></div>
    <div class="col-md-3"><div class="kpi"><div class="lbl">Valor total</div><div class="num">R$ {{ "{:,.0f}".format(kpis.valor or 0).replace(",","X").replace(".",",").replace("X",".") }}</div></div></div>
  </div>

  <div class="row g-3 mb-4">
    <div class="col-lg-8"><div class="card-chart"><h5>Nomeações por mês</h5><canvas id="chartMes"></canvas></div></div>
    <div class="col-lg-4"><div class="card-chart"><h5>Por situação</h5><canvas id="chartSit"></canvas></div></div>
  </div>

  <div class="row g-3 mb-4">
    <div class="col-lg-6"><div class="card-chart"><h5>Por tribunal</h5><canvas id="chartTrib"></canvas></div></div>
    <div class="col-lg-6"><div class="card-chart"><h5>Top 10 profissões</h5><canvas id="chartProf"></canvas></div></div>
  </div>

  <div class="row g-3 mb-4">
    <div class="col-12"><div class="card-chart"><h5>Top 20 varas com mais nomeações</h5><canvas id="chartVaras"></canvas></div></div>
  </div>

  <div class="row g-3">
    <div class="col-12"><div class="card-chart"><h5>Top 15 profissionais mais nomeados</h5><canvas id="chartTop"></canvas></div></div>
  </div>
</div>

<script>
const PD_NAVY = '#1E3A2A', PD_GOLD = '#B8941F', PD_NAVY2='#142821', PD_GREEN='#16A34A';
const cores = ['#1E3A2A','#B8941F','#16A34A','#2E5540','#8F6E17','#0F6E31','#426F57','#6B5110','#1C8440','#8D9B8E','#D4AB2D','#366B49','#A68125','#145731','#B29C5D'];
Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
Chart.defaults.color = '#2b2b2b';

new Chart(document.getElementById('chartMes'), {
  type: 'line', data: {
    labels: {{ mes_labels|tojson }},
    datasets: [{ label: 'Nomeações', data: {{ mes_vals|tojson }},
      borderColor: PD_NAVY, backgroundColor: 'rgba(26,40,71,.12)', fill: true, tension: .3, pointBackgroundColor: PD_GOLD, pointRadius: 3 }]
  }, options: { responsive: true, plugins: { legend: { display: false } } }
});

new Chart(document.getElementById('chartSit'), {
  type: 'doughnut', data: {
    labels: {{ sit_labels|tojson }},
    datasets: [{ data: {{ sit_vals|tojson }}, backgroundColor: cores, borderWidth: 2, borderColor: '#fff' }]
  }, options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
});

new Chart(document.getElementById('chartTrib'), {
  type: 'bar', data: {
    labels: {{ trib_labels|tojson }},
    datasets: [{ label: 'Nomeações', data: {{ trib_vals|tojson }}, backgroundColor: PD_NAVY, borderRadius: 4 }]
  }, options: { responsive: true, plugins: { legend: { display: false } } }
});

new Chart(document.getElementById('chartProf'), {
  type: 'bar', data: {
    labels: {{ prof_labels|tojson }},
    datasets: [{ label: 'Nomeações', data: {{ prof_vals|tojson }}, backgroundColor: PD_GOLD, borderRadius: 4 }]
  }, options: { indexAxis: 'y', responsive: true, plugins: { legend: { display: false } } }
});

new Chart(document.getElementById('chartTop'), {
  type: 'bar', data: {
    labels: {{ top_labels|tojson }},
    datasets: [{ label: 'Nomeações', data: {{ top_vals|tojson }}, backgroundColor: PD_NAVY2, borderRadius: 4 }]
  }, options: { indexAxis: 'y', responsive: true, plugins: { legend: { display: false } } }
});

new Chart(document.getElementById('chartVaras'), {
  type: 'bar', data: {
    labels: {{ vara_labels|tojson }},
    datasets: [{ label: 'Nomeações', data: {{ vara_vals|tojson }}, backgroundColor: PD_NAVY, borderRadius: 4 }]
  }, options: { indexAxis: 'y', responsive: true, plugins: { legend: { display: false } },
    scales: { y: { ticks: { autoSkip: false, font: { size: 11 } } } } }
});
</script>
</body></html>
"""


@app.route("/dashboard")
def dashboard():
    where, params, filtros = _build_query(request.args)
    join = """
        FROM nomeacao n
          JOIN tribunal t     ON t.id = n.tribunal_id
          JOIN unidade u      ON u.id = n.unidade_id
          JOIN profissional p ON p.id = n.profissional_id
    """
    # concatena where existente com uma condição adicional
    def _and(cond):
        return (where + " AND " if where else "WHERE ") + cond

    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(f"""
            SELECT COUNT(*), COUNT(DISTINCT n.profissional_id),
                   COALESCE(SUM(n.valor),0), COUNT(DISTINCT n.tribunal_id)
            {join} {where}
        """, params)
        total, pessoas, valor, n_trib = cur.fetchone()

        cur.execute(f"""
            SELECT to_char(n.data_nomeacao,'YYYY-MM'), COUNT(*)
            {join} {_and('n.data_nomeacao IS NOT NULL')}
            GROUP BY 1 ORDER BY 1
        """, params)
        mes = cur.fetchall()

        cur.execute(f"""
            SELECT n.situacao, COUNT(*)
            {join} {_and('n.situacao IS NOT NULL')}
            GROUP BY 1 ORDER BY 2 DESC
        """, params)
        sit = cur.fetchall()

        cur.execute(f"SELECT t.sigla, COUNT(*) {join} {where} GROUP BY t.sigla ORDER BY 2 DESC", params)
        trib = cur.fetchall()

        cur.execute(f"""
            SELECT p.profissao, COUNT(*)
            {join} {_and("p.profissao IS NOT NULL AND p.profissao<>''")}
            GROUP BY p.profissao ORDER BY 2 DESC LIMIT 10
        """, params)
        prof = cur.fetchall()

        cur.execute(f"SELECT p.nome, COUNT(*) {join} {where} GROUP BY p.nome ORDER BY 2 DESC LIMIT 15", params)
        top = cur.fetchall()

        cur.execute(f"""
            SELECT t.sigla || ' — ' || u.nome, COUNT(*)
            {join} {where}
            GROUP BY t.sigla, u.nome ORDER BY 2 DESC LIMIT 20
        """, params)
        vara = cur.fetchall()

        cur.execute("SELECT sigla FROM tribunal ORDER BY sigla")
        tribunais_opts = [r[0] for r in cur.fetchall()]
        cur.execute("""
            SELECT DISTINCT profissao FROM profissional
             WHERE profissao IS NOT NULL AND profissao<>''
             ORDER BY profissao
        """)
        profissoes_opts = [r[0] for r in cur.fetchall()]

    return render_template_string(
        DASH_TPL,
        filtros=filtros,
        tribunais=tribunais_opts, profissoes=profissoes_opts,
        query_string=request.query_string.decode(),
        kpis={"total": total, "pessoas": pessoas, "tribunais": n_trib, "valor": float(valor or 0)},
        mes_labels=[r[0] for r in mes], mes_vals=[r[1] for r in mes],
        sit_labels=[r[0] for r in sit], sit_vals=[r[1] for r in sit],
        trib_labels=[r[0] for r in trib], trib_vals=[r[1] for r in trib],
        prof_labels=[r[0] for r in prof], prof_vals=[r[1] for r in prof],
        top_labels=[(r[0] or '')[:40] for r in top], top_vals=[r[1] for r in top],
        vara_labels=[(r[0] or '')[:80] for r in vara], vara_vals=[r[1] for r in vara],
    )


# ------------------------- Relatório imprimível (PDF) ------------------------- #

RELATORIO_TPL = """
<!doctype html><html lang="pt-br"><head>
<meta charset="utf-8"><title>Relatório · Peritus Dominus</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
  @page { size: A4; margin: 18mm 14mm; }
  * { box-sizing: border-box; }
  html, body { background: #fff; color: #2b2b2b; margin: 0; }
  body { font-family: 'Inter', system-ui, sans-serif; font-size: 11pt; }
  h1, h2, h3, .brand { font-family: 'Cormorant Garamond', 'Times New Roman', serif; }
  .wrap { max-width: 190mm; margin: 0 auto; padding: 24px 16px; }

  .cabec { display: flex; justify-content: space-between; align-items: flex-start;
           border-bottom: 2px solid #B8941F; padding-bottom: 14px; margin-bottom: 18px; }
  .brand { font-size: 1.6rem; color: #1E3A2A; font-weight: 700; margin: 0; }
  .brand small { display: block; color: #8b8477; font-family: 'Inter', sans-serif;
                 font-size: .72rem; letter-spacing: 2px; text-transform: uppercase; font-weight: 500; }
  .meta { text-align: right; font-size: .78rem; color: #555; line-height: 1.5; }

  .titulo-relatorio { font-size: 1.6rem; color: #1E3A2A; margin: 10px 0 4px; }
  .subtitulo { color: #8b8477; font-size: .9rem; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 18px; }

  .filtros-aplicados {
    background: #F5F0E6; border-left: 3px solid #B8941F; padding: 10px 14px;
    font-size: .85rem; color: #4a4a4a; margin-bottom: 18px;
  }
  .filtros-aplicados strong { color: #1E3A2A; }

  .kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 22px; }
  .kpi-box { border: 1px solid #e9e4d6; border-top: 3px solid #B8941F; padding: 10px 14px; border-radius: 4px; }
  .kpi-box .lbl { color: #8b8477; font-size: .68rem; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 600; }
  .kpi-box .num { font-family: 'Cormorant Garamond', serif; font-size: 1.7rem; color: #1E3A2A; font-weight: 700; }

  .section-title { font-family: 'Inter', sans-serif; color: #1E3A2A; font-size: .85rem;
                   text-transform: uppercase; letter-spacing: 2px; font-weight: 600;
                   border-bottom: 1px solid #B8941F; padding-bottom: 6px; margin: 20px 0 10px; }

  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
  .chart-card { border: 1px solid #e9e4d6; padding: 10px 12px 6px; border-radius: 4px; }
  .chart-card h4 { font-size: .95rem; color: #1E3A2A; margin: 2px 0 8px; }
  canvas { max-height: 230px; }

  table { width: 100%; border-collapse: collapse; font-size: .78rem; }
  th, td { padding: 6px 8px; border-bottom: 1px solid #e9e4d6; text-align: left; }
  th { background: #1E3A2A; color: #fff; font-weight: 600; letter-spacing: .5px; }

  .rodape { margin-top: 28px; padding-top: 10px; border-top: 1px solid #e9e4d6;
            font-size: .72rem; color: #8b8477; display: flex; justify-content: space-between; }

  .no-print { position: fixed; top: 12px; right: 12px; z-index: 100; }
  .no-print button {
    background: #1E3A2A; color: #fff; border: 0; padding: 10px 20px;
    border-radius: 4px; cursor: pointer; font-weight: 600; letter-spacing: .5px;
    box-shadow: 0 2px 8px rgba(0,0,0,.15);
  }
  .no-print button:hover { background: #142821; }
  @media print { .no-print { display: none !important; } .page-break { page-break-before: always; } }
</style></head><body>

<div class="no-print">
  <button onclick="window.print()">📄 Imprimir / Salvar PDF</button>
</div>

<div class="wrap">
  <div class="cabec">
    <div>
      <h1 class="brand">Peritus Dominus
        <small>Nomeações SIGEO · Justiça do Trabalho</small>
      </h1>
    </div>
    <div class="meta">
      <strong>Relatório emitido em</strong><br>
      {{ emitido_em }}<br>
      Fonte: SIGEO/CNJ (público)
    </div>
  </div>

  <div class="titulo-relatorio">Relatório de Nomeações Periciais</div>
  <div class="subtitulo">
    {% if filtros.data_ini or filtros.data_fim %}
      Período: {{ filtros.data_ini or '—' }} a {{ filtros.data_fim or '—' }}
    {% else %}
      Todo o período disponível
    {% endif %}
  </div>

  <div class="filtros-aplicados">
    <strong>Filtros aplicados:</strong>
    {% set partes = [] %}
    {% if filtros.tribunal %}{% set _ = partes.append('Tribunal: ' ~ filtros.tribunal) %}{% endif %}
    {% if filtros.unidade %}{% set _ = partes.append('Unidade: ' ~ filtros.unidade) %}{% endif %}
    {% if filtros.nome %}{% set _ = partes.append('Perito: ' ~ filtros.nome) %}{% endif %}
    {% if filtros.profissao %}{% set _ = partes.append('Profissão: ' ~ filtros.profissao) %}{% endif %}
    {% if filtros.validas == '1' %}{% set _ = partes.append('Excluídas as CANCELADA') %}{% endif %}
    {{ partes|join(' · ') or 'nenhum filtro específico' }}
  </div>

  <div class="kpi-row">
    <div class="kpi-box"><div class="lbl">Nomeações</div><div class="num">{{ "{:,}".format(kpis.total).replace(",",".") }}</div></div>
    <div class="kpi-box"><div class="lbl">Profissionais</div><div class="num">{{ "{:,}".format(kpis.pessoas).replace(",",".") }}</div></div>
    <div class="kpi-box"><div class="lbl">Tribunais</div><div class="num">{{ kpis.tribunais }}</div></div>
    <div class="kpi-box"><div class="lbl">Valor total</div><div class="num">R$ {{ "{:,.0f}".format(kpis.valor or 0).replace(",","X").replace(".",",").replace("X",".") }}</div></div>
  </div>

  <div class="section-title">Distribuição temporal</div>
  <div class="chart-card"><h4>Nomeações por mês</h4><canvas id="chartMes"></canvas></div>

  <div class="grid-2" style="margin-top: 16px;">
    <div class="chart-card"><h4>Por situação</h4><canvas id="chartSit"></canvas></div>
    <div class="chart-card"><h4>Por tribunal</h4><canvas id="chartTrib"></canvas></div>
  </div>

  <div class="page-break"></div>
  <div class="section-title">Rankings</div>

  <div class="chart-card" style="margin-bottom: 14px;"><h4>Top 10 profissões</h4><canvas id="chartProf"></canvas></div>
  <div class="chart-card" style="margin-bottom: 14px;"><h4>Top 15 profissionais mais nomeados</h4><canvas id="chartTop"></canvas></div>

  <div class="section-title">Resumo tabular</div>
  <table>
    <thead><tr><th>#</th><th>Profissional</th><th>Nomeações</th></tr></thead>
    <tbody>
    {% for i in range(top_labels|length) %}
      <tr><td>{{ i+1 }}</td><td>{{ top_labels[i] }}</td><td>{{ top_vals[i] }}</td></tr>
    {% endfor %}
    </tbody>
  </table>

  <div class="rodape">
    <div>Peritus Dominus · peritusdominus.com.br</div>
    <div>Página gerada automaticamente — dados oficiais SIGEO</div>
  </div>
</div>

<script>
const PD_NAVY = '#1E3A2A', PD_GOLD = '#B8941F';
const cores = ['#1E3A2A','#B8941F','#16A34A','#2E5540','#8F6E17','#0F6E31','#426F57','#6B5110','#1C8440','#8D9B8E'];
Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
Chart.defaults.animation = false;

new Chart(document.getElementById('chartMes'), {
  type: 'line', data: {
    labels: {{ mes_labels|tojson }},
    datasets: [{ data: {{ mes_vals|tojson }}, borderColor: PD_NAVY, backgroundColor: 'rgba(26,40,71,.12)', fill: true, tension: .3 }]
  }, options: { plugins: { legend: { display: false } }, maintainAspectRatio: false }
});
new Chart(document.getElementById('chartSit'), {
  type: 'doughnut', data: {
    labels: {{ sit_labels|tojson }},
    datasets: [{ data: {{ sit_vals|tojson }}, backgroundColor: cores }]
  }, options: { plugins: { legend: { position: 'bottom', labels: { font: { size: 10 } } } }, maintainAspectRatio: false }
});
new Chart(document.getElementById('chartTrib'), {
  type: 'bar', data: {
    labels: {{ trib_labels|tojson }},
    datasets: [{ data: {{ trib_vals|tojson }}, backgroundColor: PD_NAVY }]
  }, options: { plugins: { legend: { display: false } }, maintainAspectRatio: false }
});
new Chart(document.getElementById('chartProf'), {
  type: 'bar', data: {
    labels: {{ prof_labels|tojson }},
    datasets: [{ data: {{ prof_vals|tojson }}, backgroundColor: PD_GOLD }]
  }, options: { indexAxis: 'y', plugins: { legend: { display: false } }, maintainAspectRatio: false }
});
new Chart(document.getElementById('chartTop'), {
  type: 'bar', data: {
    labels: {{ top_labels|tojson }},
    datasets: [{ data: {{ top_vals|tojson }}, backgroundColor: PD_NAVY }]
  }, options: { indexAxis: 'y', plugins: { legend: { display: false } }, maintainAspectRatio: false }
});
</script>
</body></html>
"""


@app.route("/relatorio")
def relatorio():
    """Versão imprimível com os mesmos filtros do dashboard."""
    where, params, filtros = _build_query(request.args)
    join = """
        FROM nomeacao n
          JOIN tribunal t     ON t.id = n.tribunal_id
          JOIN unidade u      ON u.id = n.unidade_id
          JOIN profissional p ON p.id = n.profissional_id
    """
    def _and(cond):
        return (where + " AND " if where else "WHERE ") + cond

    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(f"""
            SELECT COUNT(*), COUNT(DISTINCT n.profissional_id),
                   COALESCE(SUM(n.valor),0), COUNT(DISTINCT n.tribunal_id)
            {join} {where}
        """, params)
        total, pessoas, valor, n_trib = cur.fetchone()

        cur.execute(f"SELECT to_char(n.data_nomeacao,'YYYY-MM'), COUNT(*) {join} {_and('n.data_nomeacao IS NOT NULL')} GROUP BY 1 ORDER BY 1", params)
        mes = cur.fetchall()
        cur.execute(f"SELECT n.situacao, COUNT(*) {join} {_and('n.situacao IS NOT NULL')} GROUP BY 1 ORDER BY 2 DESC", params)
        sit = cur.fetchall()
        cur.execute(f"SELECT t.sigla, COUNT(*) {join} {where} GROUP BY t.sigla ORDER BY 2 DESC", params)
        trib = cur.fetchall()
        _cond_prof = _and("p.profissao IS NOT NULL AND p.profissao<>''")
        cur.execute(f"SELECT p.profissao, COUNT(*) {join} {_cond_prof} GROUP BY p.profissao ORDER BY 2 DESC LIMIT 10", params)
        prof = cur.fetchall()
        cur.execute(f"SELECT p.nome, COUNT(*) {join} {where} GROUP BY p.nome ORDER BY 2 DESC LIMIT 15", params)
        top = cur.fetchall()

    return render_template_string(
        RELATORIO_TPL,
        filtros=filtros,
        emitido_em=datetime.now().strftime("%d/%m/%Y às %H:%M"),
        kpis={"total": total, "pessoas": pessoas, "tribunais": n_trib, "valor": float(valor or 0)},
        mes_labels=[r[0] for r in mes], mes_vals=[r[1] for r in mes],
        sit_labels=[r[0] for r in sit], sit_vals=[r[1] for r in sit],
        trib_labels=[r[0] for r in trib], trib_vals=[r[1] for r in trib],
        prof_labels=[r[0] for r in prof], prof_vals=[r[1] for r in prof],
        top_labels=[(r[0] or '')[:50] for r in top], top_vals=[r[1] for r in top],
    )


#  ---------------- Assinaturas (webhook Kiwify + admin) ---------------- #

import os
import hmac
import hashlib
import json

from flask import jsonify, abort, Response as _Resp, request as _req
from dotenv import load_dotenv as _load_dotenv

from . import assinaturas as _assin

# Garante que o .env está carregado (idempotente)
_load_dotenv()


def _get_admin_password() -> str:
    return os.environ.get("ADMIN_PASSWORD", "")


def _get_kiwify_token() -> str:
    return os.environ.get("KIWIFY_WEBHOOK_TOKEN", "")


def _valida_assinatura_kiwify(req) -> bool:
    """A Kiwify envia a assinatura HMAC-SHA1 na querystring (?signature=...).
    Se KIWIFY_WEBHOOK_TOKEN não estiver setado, aceita tudo (modo dev).
    """
    token = _get_kiwify_token()
    if not token:
        return True
    sig = req.args.get("signature") or req.headers.get("X-Kiwify-Signature") or ""
    if not sig:
        return False
    calc = hmac.new(
        token.encode("utf-8"),
        req.get_data(),
        hashlib.sha1,
    ).hexdigest()
    return hmac.compare_digest(sig, calc)


@app.route("/webhook/kiwify", methods=["POST"])
def webhook_kiwify():
    if not _valida_assinatura_kiwify(_req):
        return jsonify({"ok": False, "erro": "assinatura inválida"}), 401
    try:
        payload = _req.get_json(force=True, silent=True) or json.loads(_req.get_data() or b"{}")
    except Exception as e:
        return jsonify({"ok": False, "erro": f"payload inválido: {e}"}), 400
    resultado = _assin.processar_webhook_kiwify(payload)
    status = 200 if resultado.get("ok") else 400
    return jsonify(resultado), status


def _check_admin():
    auth = _req.authorization
    pwd = _get_admin_password()
    if not pwd:
        abort(503, "ADMIN_PASSWORD não configurado no .env")
    if not auth or auth.username != "admin" or auth.password != pwd:
        return _Resp(
            "Login necessário", 401,
            {"WWW-Authenticate": 'Basic realm="Peritus Admin"'},
        )
    return None


ADMIN_TPL = """
<!doctype html><html lang=pt-br><head><meta charset=utf-8>
<title>Assinantes · Peritus Dominus</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>body{padding:20px}</style></head><body>
<h1>Assinantes — Peritus Dominus · Nomeações SIGEO</h1>
<p class=text-muted>{{ ativos }} ativos / {{ total }} totais ·
   <a href="/admin/regenerar">Forçar regeração do ngrok</a></p>
<table class="table table-striped table-sm">
<thead><tr><th>Email</th><th>Nome</th><th>Status</th><th>Order</th>
  <th>Criado em</th><th>Atualizado</th><th>Cancelado</th></tr></thead><tbody>
{% for a in itens %}
<tr>
  <td>{{ a.email }}</td>
  <td>{{ a.nome or '' }}</td>
  <td><span class="badge
     {% if a.status=='ativo' %}bg-success{% else %}bg-secondary{% endif %}">
     {{ a.status }}</span></td>
  <td>{{ a.kiwify_order_id or '' }}</td>
  <td>{{ a.criado_em.strftime('%d/%m/%Y %H:%M') if a.criado_em else '' }}</td>
  <td>{{ a.atualizado_em.strftime('%d/%m/%Y %H:%M') if a.atualizado_em else '' }}</td>
  <td>{{ a.cancelado_em.strftime('%d/%m/%Y %H:%M') if a.cancelado_em else '' }}</td>
</tr>
{% endfor %}
</tbody></table></body></html>
"""


@app.route("/admin/assinantes")
def admin_assinantes():
    bloq = _check_admin()
    if bloq is not None:
        return bloq
    itens = _assin.listar_todos()
    ativos = sum(1 for a in itens if a["status"] == "ativo")
    return render_template_string(
        ADMIN_TPL, itens=itens, total=len(itens), ativos=ativos,
    )


@app.route("/admin/regenerar")
def admin_regenerar():
    bloq = _check_admin()
    if bloq is not None:
        return bloq
    _assin.regenerar_ngrok_yml()
    ok = _assin.reload_ngrok()
    return jsonify({"ok": True, "ngrok_reiniciado": ok,
                    "emails": _assin._emails_ativos()})


def main(host: str = "127.0.0.1", port: int = 5001):
    app.run(host=host, port=port, debug=False)
