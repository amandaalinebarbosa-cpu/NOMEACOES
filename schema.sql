-- Banco de dados de nomeações SIGEO (Justiça do Trabalho)
-- Fonte: https://aj.sigeo.jt.jus.br/aj2/internetaberto/consultapublicanomeacoes.jsf

CREATE TABLE IF NOT EXISTS tribunal (
    id           SERIAL PRIMARY KEY,
    sigla        TEXT UNIQUE NOT NULL,   -- ex.: TRT1, TRT2, TST
    nome         TEXT
);

CREATE TABLE IF NOT EXISTS nomeado (
    id           SERIAL PRIMARY KEY,
    cpf          TEXT UNIQUE,            -- pode vir mascarado; guarde como veio
    nome         TEXT NOT NULL,
    UNIQUE (nome, cpf)
);

CREATE TABLE IF NOT EXISTS orgao_julgador (
    id           SERIAL PRIMARY KEY,
    tribunal_id  INT REFERENCES tribunal(id) ON DELETE CASCADE,
    nome         TEXT NOT NULL,
    UNIQUE (tribunal_id, nome)
);

CREATE TABLE IF NOT EXISTS nomeacao (
    id                 BIGSERIAL PRIMARY KEY,
    tribunal_id        INT  REFERENCES tribunal(id),
    orgao_julgador_id  INT  REFERENCES orgao_julgador(id),
    nomeado_id         INT  REFERENCES nomeado(id),
    processo           TEXT,
    tipo_funcao        TEXT,             -- perito, assistente técnico, leiloeiro, etc.
    especialidade      TEXT,
    data_nomeacao      DATE,
    situacao           TEXT,
    valor              NUMERIC(14,2),
    magistrado         TEXT,
    fonte_url          TEXT,
    raw                JSONB,             -- payload bruto da linha (para auditoria)
    coletado_em        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tribunal_id, processo, nomeado_id, data_nomeacao, tipo_funcao)
);

CREATE INDEX IF NOT EXISTS idx_nomeacao_data     ON nomeacao (data_nomeacao);
CREATE INDEX IF NOT EXISTS idx_nomeacao_tribunal ON nomeacao (tribunal_id);
CREATE INDEX IF NOT EXISTS idx_nomeacao_tipo     ON nomeacao (tipo_funcao);
CREATE INDEX IF NOT EXISTS idx_nomeado_nome_trgm ON nomeado USING gin (nome gin_trgm_ops);
-- (o índice trgm exige: CREATE EXTENSION IF NOT EXISTS pg_trgm;)

CREATE TABLE IF NOT EXISTS coleta_log (
    id             BIGSERIAL PRIMARY KEY,
    iniciada_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finalizada_em  TIMESTAMPTZ,
    tribunal       TEXT,
    data_ini       DATE,
    data_fim       DATE,
    filtros        JSONB,
    linhas_novas   INT DEFAULT 0,
    linhas_totais  INT DEFAULT 0,
    status         TEXT,
    erro           TEXT
);
