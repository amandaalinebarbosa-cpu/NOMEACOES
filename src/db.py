"""Acesso ao PostgreSQL."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://sigeo:sigeo@localhost:5432/sigeo"
)


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
        ON CONFLICT (sigla) DO UPDATE
          SET nome = COALESCE(EXCLUDED.nome, tribunal.nome)
        RETURNING id
        """,
        (sigla, nome),
    )
    return cur.fetchone()[0]


def upsert_unidade(cur, tribunal_id: int, nome: str) -> int:
    cur.execute(
        """
        INSERT INTO unidade (tribunal_id, nome) VALUES (%s, %s)
        ON CONFLICT (tribunal_id, nome) DO UPDATE SET nome = EXCLUDED.nome
        RETURNING id
        """,
        (tribunal_id, nome),
    )
    return cur.fetchone()[0]


def upsert_profissional(cur, nome: str) -> int:
    cur.execute(
        """
        INSERT INTO profissional (nome) VALUES (%s)
        ON CONFLICT (nome) DO UPDATE SET nome = EXCLUDED.nome
        RETURNING id
        """,
        (nome,),
    )
    return cur.fetchone()[0]


def insert_nomeacao(cur, row: dict) -> bool:
    cur.execute(
        """
        INSERT INTO nomeacao
            (processo, tribunal_id, unidade_id, profissional_id,
             data_nomeacao, valor, situacao, fonte_url, raw)
        VALUES (%(processo)s, %(tribunal_id)s, %(unidade_id)s,
                %(profissional_id)s, %(data_nomeacao)s, %(valor)s,
                %(situacao)s, %(fonte_url)s, %(raw)s)
        ON CONFLICT (processo, profissional_id, data_nomeacao, situacao)
        DO NOTHING
        RETURNING id
        """,
        {**row, "raw": json.dumps(row.get("raw") or {}, ensure_ascii=False, default=str)},
    )
    return cur.fetchone() is not None
