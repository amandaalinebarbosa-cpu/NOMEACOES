"""Adiciona coluna 'Profissão' a um arquivo .xls/.xlsx de nomeações,
consultando a base local do SIGEO por 'Nome do profissional' (unaccent).

Uso:
    python scripts/preencher_profissao.py <entrada.xls> [saida.xlsx]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://sigeo:sigeo@localhost:5432/sigeo"
)


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python scripts/preencher_profissao.py <entrada.xls> [saida.xlsx]")
        return 2

    entrada = Path(sys.argv[1]).expanduser()
    saida = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else \
        entrada.with_name(entrada.stem + "_com_profissao.xlsx")

    df = pd.read_excel(entrada)
    if "Nome do profissional" not in df.columns:
        print("Coluna 'Nome do profissional' não encontrada. Colunas:", df.columns.tolist())
        return 2

    nomes = sorted({str(n).strip() for n in df["Nome do profissional"].dropna()})
    print(f"Lidos {len(df)} registros | nomes únicos: {len(nomes)}")

    mapa: dict[str, str] = {}
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")
        for nome in nomes:
            cur.execute(
                """
                SELECT profissao
                FROM profissional
                WHERE unaccent(lower(nome)) = unaccent(lower(%s))
                  AND profissao IS NOT NULL AND profissao <> ''
                LIMIT 1
                """,
                (nome,),
            )
            row = cur.fetchone()
            mapa[nome] = row[0] if row else ""

    df["Profissão"] = df["Nome do profissional"].map(
        lambda n: mapa.get(str(n).strip(), "")
    )

    df.to_excel(saida, index=False)
    achados = sum(1 for v in mapa.values() if v)
    print(f"Nomes com profissão: {achados}/{len(nomes)}")
    print(f"Arquivo gerado: {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
