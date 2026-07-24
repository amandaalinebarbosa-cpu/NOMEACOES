-- Banco de dados de nomeações SIGEO (Justiça do Trabalho)
-- Fonte: https://aj.sigeo.jt.jus.br/aj2/internetaberto/consultapublicanomeacoes.jsf

CREATE TABLE IF NOT EXISTS tribunal (
    id       SERIAL PRIMARY KEY,
    sigla    TEXT UNIQUE NOT NULL,   -- ex.: TRT1..TRT24
    nome     TEXT
);

CREATE TABLE IF NOT EXISTS unidade (
    id           SERIAL PRIMARY KEY,
    tribunal_id  INT REFERENCES tribunal(id) ON DELETE CASCADE,
    nome         TEXT NOT NULL,
    UNIQUE (tribunal_id, nome)
);

CREATE TABLE IF NOT EXISTS profissional (
    id         SERIAL PRIMARY KEY,
    nome       TEXT UNIQUE NOT NULL,
    profissao  TEXT   -- resumo (primeira profissão importada); ver qualificacao
);

ALTER TABLE profissional ADD COLUMN IF NOT EXISTS profissao TEXT;
CREATE INDEX IF NOT EXISTS idx_profissional_profissao ON profissional (lower(profissao));

-- Uma pessoa pode ter várias qualificações no cadastro do CNPTJ:
-- (categoria = PERITO/TRADUTOR/INTÉRPRETE, profissao, especialidade).
CREATE TABLE IF NOT EXISTS qualificacao (
    id               SERIAL PRIMARY KEY,
    profissional_id  INT REFERENCES profissional(id) ON DELETE CASCADE,
    categoria        TEXT NOT NULL,
    profissao        TEXT NOT NULL,
    especialidade    TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_qualificacao ON qualificacao
    (profissional_id, categoria, profissao, COALESCE(especialidade, ''));
CREATE INDEX IF NOT EXISTS idx_qualificacao_prof   ON qualificacao (lower(profissao));
CREATE INDEX IF NOT EXISTS idx_qualificacao_espec  ON qualificacao (lower(especialidade));

CREATE TABLE IF NOT EXISTS nomeacao (
    id               BIGSERIAL PRIMARY KEY,
    processo         TEXT,
    tribunal_id      INT REFERENCES tribunal(id),
    unidade_id       INT REFERENCES unidade(id),
    profissional_id  INT REFERENCES profissional(id),
    data_nomeacao    DATE,
    valor            NUMERIC(14,2),
    situacao         TEXT,          -- ACEITA | BAIXADA | CANCELADA | SERVIÇO PRESTADO
    fonte_url        TEXT,
    raw              JSONB,
    coletado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (processo, profissional_id, data_nomeacao, situacao)
);

CREATE INDEX IF NOT EXISTS idx_nomeacao_data      ON nomeacao (data_nomeacao);
CREATE INDEX IF NOT EXISTS idx_nomeacao_tribunal  ON nomeacao (tribunal_id);
CREATE INDEX IF NOT EXISTS idx_nomeacao_situacao  ON nomeacao (situacao);
CREATE INDEX IF NOT EXISTS idx_profissional_nome  ON profissional (lower(nome));

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
