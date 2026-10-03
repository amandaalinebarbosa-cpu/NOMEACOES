-- Tabela de assinantes do Peritus Dominus — Nomeações SIGEO
CREATE TABLE IF NOT EXISTS assinante (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    nome            TEXT,
    status          TEXT NOT NULL DEFAULT 'ativo',  -- ativo | cancelado | reembolsado
    kiwify_order_id TEXT,
    kiwify_product  TEXT,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cancelado_em    TIMESTAMPTZ,
    raw             JSONB
);

CREATE INDEX IF NOT EXISTS idx_assinante_status ON assinante (status);
CREATE INDEX IF NOT EXISTS idx_assinante_email  ON assinante (lower(email));

-- Log de todos os eventos recebidos (auditoria)
CREATE TABLE IF NOT EXISTS assinante_evento (
    id         BIGSERIAL PRIMARY KEY,
    recebido_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evento     TEXT,
    email      TEXT,
    payload    JSONB
);
