"""Acesso ao PostgreSQL."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://sigeo:sigeo@localhost:5432/sigeo")


@contextmanager
def connect():
    with psycopg.connect(DATABASE_URL, autocommit=False) as conn:
        yield conn


def init_schema() -> None:
    sql = Path(__file__).resolve().parent.parent.joinpath("schema.sql").read_text()
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()


def upsert_tribunal(cur, sigla: str, nome: str | None = None) -> int:
    cur.execute(
        """
        INSERT INTO tribunal (sigla, nome) VALUES (%s, %s)
        ON CONFLICT (sigla) DO UPDATE SET nome = COALESCE(EXCLUDED.nome, tribunal.nome)
        RETURNING id
        """,
        (sigla, nome),
    )
    return cur.fetchone()[0]


def upsert_nomeado(cur, nome: str, cpf: str | None) -> int:
    cur.execute(
        """
        INSERT INTO nomeado (nome, cpf) VALUES (%s, %s)
        ON CONFLICT (nome, cpf) DO UPDATE SET nome = EXCLUDED.nome
        RETURNING id
        """,
        (nome, cpf),
    )
    return cur.fetchone()[0]


def upsert_orgao(cur, tribunal_id: int, nome: str) -> int:
    cur.execute(
        """
        INSERT INTO orgao_julgador (tribunal_id, nome) VALUES (%s, %s)
        ON CONFLICT (tribunal_id, nome) DO UPDATE SET nome = EXCLUDED.nome
        RETURNING id
        """,
        (tribunal_id, nome),
    )
    return cur.fetchone()[0]


def insert_nomeacao(cur, row: dict) -> bool:
    """Insere nomeação. Retorna True se foi novo registro."""
    cur.execute(
        """
        INSERT INTO nomeacao
            (tribunal_id, orgao_julgador_id, nomeado_id, processo, tipo_funcao,
             especialidade, data_nomeacao, situacao, valor, magistrado, fonte_url, raw)
        VALUES (%(tribunal_id)s, %(orgao_julgador_id)s, %(nomeado_id)s, %(processo)s,
                %(tipo_funcao)s, %(especialidade)s, %(data_nomeacao)s, %(situacao)s,
                %(valor)s, %(magistrado)s, %(fonte_url)s, %(raw)s)
        ON CONFLICT (tribunal_id, processo, nomeado_id, data_nomeacao, tipo_funcao)
        DO NOTHING
        RETURNING id
        """,
        {**row, "raw": json.dumps(row.get("raw") or {}, ensure_ascii=False, default=str)},
    )
    return cur.fetchone() is not None
