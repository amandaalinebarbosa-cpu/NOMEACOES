# Nomeações SIGEO

Base de dados e coletor da consulta pública de nomeações da Justiça do Trabalho
(SIGEO): <https://aj.sigeo.jt.jus.br/aj2/internetaberto/consultapublicanomeacoes.jsf>.

Permite armazenar em PostgreSQL as nomeações filtradas por tribunal, período,
nome/CPF do nomeado e tipo de função (perito, assistente técnico, leiloeiro etc.).

## Como usar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # ajuste DATABASE_URL

# cria as tabelas
python -m src.cli init-db

# coleta com filtros
python -m src.cli coletar --tribunal TRT1 \
    --data-ini 2026-01-01 --data-fim 2026-07-24 \
    --tipo "Perito"
```

## Estrutura

- `schema.sql` — schema PostgreSQL (`tribunal`, `orgao_julgador`, `nomeado`,
  `nomeacao`, `coleta_log`).
- `src/scraper.py` — cliente HTTP para o formulário JSF/PrimeFaces do SIGEO
  (trata `javax.faces.ViewState` e resposta parcial ajax).
- `src/db.py` — upserts e conexão psycopg.
- `src/cli.py` — comandos `init-db` e `coletar`.

## ⚠️ Ajuste necessário nos IDs do formulário

O SIGEO é JSF: os campos têm ids como `formConsulta:dataInicial_input`. Como
a página bloqueia acesso automatizado ao HTML inicial (retorna 403 sem UA de
navegador), o mapeamento inicial em `FIELD_MAP` (`src/scraper.py`) usa nomes
prováveis. Antes da primeira coleta real:

1. Abra a página no navegador → DevTools → aba Network.
2. Preencha o formulário e clique em **Pesquisar**.
3. Copie os `name`/`id` reais dos inputs (aparecem no *Form Data* do POST).
4. Ajuste `FIELD_MAP` e, se necessário, os cabeçalhos usados em
   `SigeoClient.linhas()` / `cli.coletar()`.

## Boas práticas

- Respeite `REQUEST_DELAY_SECONDS` entre requisições.
- Faça coletas incrementais por intervalos curtos de data para evitar
  paginação pesada.
- O campo `raw` (JSONB) preserva a linha original — útil quando a estrutura
  da tabela mudar.
