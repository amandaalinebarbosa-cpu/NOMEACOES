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
<meta charset="utf-8"><title>Nomeações SIGEO</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  body { padding: 20px; }
  .filters { background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
  table.dataTable { font-size: 0.9rem; }
  th { position: sticky; top: 0; background: #fff; }
  .stats { display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
  .stat-card { background: #e7f1ff; padding: 10px 20px; border-radius: 8px; min-width: 150px; }
  .stat-num { font-size: 1.6rem; font-weight: 600; color: #0d6efd; }
</style>
</head><body>
<div class="container-fluid">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h1>Nomeações SIGEO — Justiça do Trabalho</h1>
    <a href="/dashboard" class="btn btn-primary">📊 Ver Dashboards</a>
  </div>

  <div class="stats">
    <div class="stat-card"><div class="stat-num">{{ "{:,}".format(total_geral).replace(",", ".") }}</div><div>total no banco</div></div>
    <div class="stat-card"><div class="stat-num">{{ "{:,}".format(total_filtrado).replace(",", ".") }}</div><div>com filtros atuais</div></div>
    <div class="stat-card"><div class="stat-num">{{ "{:,}".format(total_profissionais).replace(",", ".") }}</div><div>profissionais distintos</div></div>
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
    <div class="mt-3 d-flex gap-2">
      <button class="btn btn-primary" type="submit">Filtrar</button>
      <a class="btn btn-outline-secondary" href="/">Limpar</a>
      <a class="btn btn-success" href="/export?{{ query_string }}">📥 Baixar CSV</a>
    </div>
  </form>

  <p class="text-muted">Mostrando {{ linhas|length }} de {{ "{:,}".format(total_filtrado).replace(",", ".") }} resultados (limite {{ limite }}).</p>

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


def _build_query(args):
    clauses, params = [], []
    tribunal = args.get("tribunal") or None
    unidade = args.get("unidade") or None
    nome = args.get("nome") or None
    profissao = args.get("profissao") or None
    situacao = args.get("situacao") or None
    data_ini = args.get("data_ini") or None
    data_fim = args.get("data_fim") or None
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
    if data_ini:
        clauses.append("n.data_nomeacao >= %s"); params.append(_parse_date(data_ini))
    if data_fim:
        clauses.append("n.data_nomeacao <= %s"); params.append(_parse_date(data_fim))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    filtros = {"tribunal": tribunal, "unidade": unidade, "nome": nome,
               "profissao": profissao, "situacao": situacao,
               "data_ini": data_ini, "data_fim": data_fim}
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


DASH_TPL = """
<!doctype html>
<html lang="pt-br"><head>
<meta charset="utf-8"><title>Dashboards — Nomeações SIGEO</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
  body { padding: 20px; background: #f5f7fb; }
  .kpi { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .kpi .num { font-size: 2rem; font-weight: 700; color: #0d6efd; }
  .kpi .lbl { color: #6c757d; font-size: 0.85rem; text-transform: uppercase; letter-spacing: .5px; }
  .card-chart { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,.08); height: 100%; }
  .card-chart h5 { margin-bottom: 15px; color: #333; }
  canvas { max-height: 350px; }
</style>
</head><body>
<div class="container-fluid">
  <div class="d-flex justify-content-between align-items-center mb-4">
    <h1>📊 Dashboards</h1>
    <div><a href="/" class="btn btn-outline-primary">← Voltar à tabela</a></div>
  </div>

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

  <div class="row g-3">
    <div class="col-12"><div class="card-chart"><h5>Top 15 profissionais mais nomeados</h5><canvas id="chartTop"></canvas></div></div>
  </div>
</div>

<script>
const cores = ['#0d6efd','#6610f2','#6f42c1','#d63384','#dc3545','#fd7e14','#ffc107','#198754','#20c997','#0dcaf0','#6c757d','#adb5bd','#495057','#212529','#e83e8c'];

new Chart(document.getElementById('chartMes'), {
  type: 'line', data: {
    labels: {{ mes_labels|tojson }},
    datasets: [{ label: 'Nomeações', data: {{ mes_vals|tojson }},
      borderColor: '#0d6efd', backgroundColor: 'rgba(13,110,253,.15)', fill: true, tension: .3 }]
  }, options: { responsive: true, plugins: { legend: { display: false } } }
});

new Chart(document.getElementById('chartSit'), {
  type: 'doughnut', data: {
    labels: {{ sit_labels|tojson }},
    datasets: [{ data: {{ sit_vals|tojson }}, backgroundColor: cores }]
  }, options: { responsive: true }
});

new Chart(document.getElementById('chartTrib'), {
  type: 'bar', data: {
    labels: {{ trib_labels|tojson }},
    datasets: [{ label: 'Nomeações', data: {{ trib_vals|tojson }}, backgroundColor: '#0d6efd' }]
  }, options: { responsive: true, plugins: { legend: { display: false } } }
});

new Chart(document.getElementById('chartProf'), {
  type: 'bar', data: {
    labels: {{ prof_labels|tojson }},
    datasets: [{ label: 'Nomeações', data: {{ prof_vals|tojson }}, backgroundColor: '#20c997' }]
  }, options: { indexAxis: 'y', responsive: true, plugins: { legend: { display: false } } }
});

new Chart(document.getElementById('chartTop'), {
  type: 'bar', data: {
    labels: {{ top_labels|tojson }},
    datasets: [{ label: 'Nomeações', data: {{ top_vals|tojson }}, backgroundColor: '#fd7e14' }]
  }, options: { indexAxis: 'y', responsive: true, plugins: { legend: { display: false } } }
});
</script>
</body></html>
"""


@app.route("/dashboard")
def dashboard():
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT profissional_id), COALESCE(SUM(valor),0) FROM nomeacao")
        total, pessoas, valor = cur.fetchone()
        cur.execute("SELECT COUNT(DISTINCT tribunal_id) FROM nomeacao")
        n_trib = cur.fetchone()[0]

        cur.execute("""
            SELECT to_char(data_nomeacao,'YYYY-MM'), COUNT(*) FROM nomeacao
             WHERE data_nomeacao IS NOT NULL
             GROUP BY 1 ORDER BY 1
        """)
        mes = cur.fetchall()

        cur.execute("SELECT situacao, COUNT(*) FROM nomeacao WHERE situacao IS NOT NULL GROUP BY 1 ORDER BY 2 DESC")
        sit = cur.fetchall()

        cur.execute("""
            SELECT t.sigla, COUNT(*) FROM nomeacao n
              JOIN tribunal t ON t.id=n.tribunal_id
             GROUP BY t.sigla ORDER BY 2 DESC
        """)
        trib = cur.fetchall()

        cur.execute("""
            SELECT profissao, COUNT(*) FROM profissional p
              JOIN nomeacao n ON n.profissional_id=p.id
             WHERE profissao IS NOT NULL AND profissao<>''
             GROUP BY profissao ORDER BY 2 DESC LIMIT 10
        """)
        prof = cur.fetchall()

        cur.execute("""
            SELECT p.nome, COUNT(*) FROM nomeacao n
              JOIN profissional p ON p.id=n.profissional_id
             GROUP BY p.nome ORDER BY 2 DESC LIMIT 15
        """)
        top = cur.fetchall()

    return render_template_string(
        DASH_TPL,
        kpis={"total": total, "pessoas": pessoas, "tribunais": n_trib, "valor": float(valor or 0)},
        mes_labels=[r[0] for r in mes], mes_vals=[r[1] for r in mes],
        sit_labels=[r[0] for r in sit], sit_vals=[r[1] for r in sit],
        trib_labels=[r[0] for r in trib], trib_vals=[r[1] for r in trib],
        prof_labels=[r[0] for r in prof], prof_vals=[r[1] for r in prof],
        top_labels=[r[0][:40] for r in top], top_vals=[r[1] for r in top],
    )


def main(host: str = "127.0.0.1", port: int = 5001):
    app.run(host=host, port=port, debug=False)
