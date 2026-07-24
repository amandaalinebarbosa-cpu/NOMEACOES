# Nomeações SIGEO

Coletor e banco de dados PostgreSQL para a consulta pública de nomeações
da Justiça do Trabalho (SIGEO/AJ-JT):
<https://aj.sigeo.jt.jus.br/aj2/internetaberto/consultapublicanomeacoes.jsf>.

## O que a página pública oferece

Filtros disponíveis no formulário:

- **Tribunal** (TRT1 a TRT24)
- **Período** (data inicial e final, dd/mm/aaaa)
- **UF / Município / Unidade** (dependentes do tribunal)
- **Situação** (CANCELADA, ACEITA, BAIXADA, SERVIÇO PRESTADO)

Colunas do resultado:

`Número do processo | Tribunal | Unidade | Nome do profissional | Data | Valor | Situação`

> A página **não** permite filtrar por nome/CPF do profissional nem por
> tipo de função (perito, leiloeiro etc.). Coletamos por período/tribunal
> e, depois, filtramos por nome/CPF com o comando `buscar` no banco local.

## Uso

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # ajuste DATABASE_URL

# cria as tabelas
python -m src.cli init-db

# coleta por tribunal e período
python -m src.cli coletar --tribunal TRT2 \
    --data-ini 2026-01-01 --data-fim 2026-01-31

# coleta só situações específicas
python -m src.cli coletar --tribunal TRT2 \
    --data-ini 2026-06-01 --data-fim 2026-06-30 \
    --situacao ACEITA --situacao SERVICO_PRESTADO

# busca local — SIGEO não filtra por nome, mas o banco sim
python -m src.cli buscar --nome "silva" --tribunal TRT2
```

## Estrutura

- `schema.sql` — `tribunal`, `unidade`, `profissional`, `nomeacao`,
  `coleta_log`. `nomeacao.raw` guarda o JSON bruto da linha.
- `src/scraper.py` — cliente HTTP para o formulário JSF/PrimeFaces.
  Mantém `javax.faces.ViewState`, envia POST como `Faces-Request:
  partial/ajax` e extrai o `<update id="form:resultadoPesquisa">` da
  resposta parcial. Contém o mapeamento `TRIBUNAIS` (sigla → id JSF).
- `src/db.py` — conexão psycopg + upserts.
- `src/cli.py` — comandos `init-db`, `coletar`, `buscar`.

## Notas operacionais

- Respeite `REQUEST_DELAY_SECONDS` (padrão 1,5s) entre requisições.
- Faça coletas por intervalos curtos (uma semana ou um mês) para evitar
  timeouts e paginação pesada.
- Paginação ainda não está implementada — o padrão do PrimeFaces é 25
  linhas por página; se o intervalo devolver mais que isso, ajuste o
  período ou implemente o clique nas páginas seguintes
  (`form:resultadoPesquisa_paginator_bottom`).
