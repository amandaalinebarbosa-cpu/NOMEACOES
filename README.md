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

# coleta por tribunal e período (com paginação)
python -m src.cli coletar --tribunal TRT2 \
    --data-ini 2026-01-01 --data-fim 2026-01-31

# baixa toda a base disponível, mês a mês, para todos os TRTs
python -m src.cli backfill --data-ini 2015-01-01

# coleta apenas o mês anterior (para rodar dia 1º de cada mês)
python -m src.cli coletar-mes-anterior

# coleta só situações específicas
python -m src.cli coletar --tribunal TRT2 \
    --data-ini 2026-06-01 --data-fim 2026-06-30 \
    --situacao ACEITA --situacao SERVICO_PRESTADO

# busca local — SIGEO não filtra por nome, mas o banco sim
python -m src.cli buscar --nome "silva" --tribunal TRT2
python -m src.cli buscar --profissao "perito medico"

# a profissão não vem do SIGEO — preencha manualmente ou por CSV
python -m src.cli set-profissao --nome "JOSE DA SILVA" --profissao "Perito Médico" --exato
python -m src.cli import-profissoes profissoes.csv   # cabeçalho: nome,profissao

# importa cadastro CNPTJ (TSV: Nome\tCategoria\tProfissão\tEspecialidade)
python -m src.cli import-peritos data/peritos.tsv
```

## Cadastro nacional (CNPTJ)

Salve o cadastro colado (Nome | Categoria | Profissão | Especialidade) em
`data/peritos.tsv` (separado por TAB, primeira linha pode ser o cabeçalho).
O comando `import-peritos` cria/atualiza `profissional` e insere uma linha
em `qualificacao` para cada combinação categoria/profissão/especialidade.
Isso permite consultar por profissão e especialidade sem depender do que o
SIGEO devolve na nomeação.

## Estrutura

- `schema.sql` — `tribunal`, `unidade`, `profissional`, `nomeacao`,
  `coleta_log`. `nomeacao.raw` guarda o JSON bruto da linha.
- `src/scraper.py` — cliente HTTP para o formulário JSF/PrimeFaces.
  Mantém `javax.faces.ViewState`, envia POST como `Faces-Request:
  partial/ajax` e extrai o `<update id="form:resultadoPesquisa">` da
  resposta parcial. Contém o mapeamento `TRIBUNAIS` (sigla → id JSF).
- `src/db.py` — conexão psycopg + upserts.
- `src/cli.py` — comandos `init-db`, `coletar`, `buscar`.

## Agendamento mensal

`.github/workflows/coleta-mensal.yml` roda `coletar-mes-anterior` todo dia 1º
às 05:00 UTC (02:00 BRT). Requer o secret `DATABASE_URL` configurado no
repositório (Settings → Secrets and variables → Actions). O mesmo workflow
pode ser disparado manualmente em `Actions → Coleta mensal SIGEO → Run
workflow` com modo `backfill` para o carregamento histórico inicial.

Se preferir rodar em servidor próprio, use cron:

```cron
0 3 1 * *  cd /caminho/NOMEACOES && /caminho/.venv/bin/python -m src.cli coletar-mes-anterior >> logs/coleta.log 2>&1
```

## Notas operacionais

- Respeite `REQUEST_DELAY_SECONDS` (padrão 1,5s) entre requisições.
- Faça coletas por intervalos curtos (uma semana ou um mês) para evitar
  timeouts e paginação pesada.
- Paginação ainda não está implementada — o padrão do PrimeFaces é 25
  linhas por página; se o intervalo devolver mais que isso, ajuste o
  período ou implemente o clique nas páginas seguintes
  (`form:resultadoPesquisa_paginator_bottom`).
