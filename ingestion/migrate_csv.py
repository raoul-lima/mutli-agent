"""Chargement des CSV métier dans PostgreSQL (`grossiste_mada`).

Lancement : `python -m ingestion.migrate_csv [--append]` depuis la racine du projet.
Sans `--append`, les tables sont vidées avant insertion.
"""

import os
import sys

import pandas as pd
from sqlalchemy import text

from configs import DB_NAME_BUSINESS, PATH_CSV, get_engine_business

# Ordre de dépendance des clés étrangères : les parents d'abord.
# Plusieurs noms de fichiers sont acceptés par table (tolérance aux fautes de frappe).
TABLES = [
    ("employees", ["employees.csv"]),
    ("products", ["products.csv"]),
    ("customers", ["customers.csv", "customres.csv"]),
    ("orders", ["orders.csv"]),
    ("sales", ["sales.csv"]),
]

NUMERIC_TYPES = {"numeric", "integer", "bigint", "smallint", "real", "double precision"}
DATE_TYPES = {"date", "timestamp without time zone", "timestamp with time zone"}


def foreign_keys(conn):
    """Les contraintes réelles de la base, plutôt qu'une liste codée en dur."""
    rows = conn.execute(
        text(
            "SELECT tc.table_name, kcu.column_name, ccu.table_name, ccu.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON kcu.constraint_name = tc.constraint_name "
            "JOIN information_schema.constraint_column_usage ccu "
            "  ON ccu.constraint_name = tc.constraint_name "
            "WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'"
        )
    ).fetchall()
    return [tuple(r) for r in rows]


def check_foreign_keys(conn, frames):
    """Vérifie l'intégrité référentielle avant l'insertion : l'erreur brute de
    PostgreSQL ne signale que la première valeur fautive, noyée dans tout le SQL."""
    problems = []
    for table, column, ref_table, ref_column in foreign_keys(conn):
        if table not in frames or ref_table not in frames:
            continue
        known = set(frames[ref_table][ref_column].dropna())
        used = frames[table][column].dropna()
        orphans = sorted(set(used) - known)
        if orphans:
            problems.append(
                f"{table}.{column} -> {ref_table}.{ref_column} : "
                f"{len(orphans)} valeur(s) inconnue(s) {orphans[:5]}"
            )
    return problems


def db_column_types(conn, table_name):
    rows = conn.execute(
        text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t"
        ),
        {"t": table_name},
    ).fetchall()
    return {name: dtype for name, dtype in rows}


def find_csv(candidates):
    for name in candidates:
        path = os.path.join(PATH_CSV, name)
        if os.path.exists(path):
            return path
    return None


def clean_numeric(series, table, column):
    """'2 500 000' -> 2500000. Les séparateurs de milliers cassent l'insertion en NUMERIC."""
    # Motif construit sans échappement \u : le moteur regex d'Arrow ne le supporte pas.
    spaces = "[\\s\u00a0\u202f]"
    cleaned = (
        series.astype("string")
        .str.replace(spaces, "", regex=True)
        .str.replace(",", ".", regex=False)
    )
    converted = pd.to_numeric(cleaned, errors="coerce")

    invalid = series[converted.isna() & series.notna()]
    if not invalid.empty:
        raise ValueError(
            f"{table}.{column} : {len(invalid)} valeur(s) non numérique(s), "
            f"ex. {invalid.unique()[:3].tolist()}"
        )
    return converted


def prepare_table(conn, table, csv_file):
    df = pd.read_csv(csv_file, dtype=str, keep_default_na=True)
    df.columns = df.columns.str.lower().str.strip()

    types = db_column_types(conn, table)
    if not types:
        raise ValueError(f"la table '{table}' n'existe pas dans {DB_NAME_BUSINESS}")

    missing = set(types) - set(df.columns)
    extra = set(df.columns) - set(types)
    if missing or extra:
        details = []
        if missing:
            details.append(f"absentes du CSV : {sorted(missing)}")
        if extra:
            details.append(f"inconnues en base : {sorted(extra)}")
        raise ValueError(f"colonnes incohérentes ({'; '.join(details)})")

    for column, dtype in types.items():
        if df[column].dtype == object or str(df[column].dtype) == "string":
            df[column] = df[column].str.strip()
        if dtype in NUMERIC_TYPES:
            df[column] = clean_numeric(df[column], table, column)
        elif dtype in DATE_TYPES:
            df[column] = pd.to_datetime(df[column], errors="coerce").dt.date

    return df[list(types)]


def main():
    append = "--append" in sys.argv

    plan = []
    for table, candidates in TABLES:
        csv_file = find_csv(candidates)
        if csv_file is None:
            print(f"Fichier introuvable pour '{table}' dans {PATH_CSV} "
                  f"(cherché : {', '.join(candidates)})")
            return 1
        plan.append((table, csv_file))

    print(f"Migration vers la base {DB_NAME_BUSINESS}\n")

    # Une seule transaction : en cas d'échec, la base reste dans son état initial.
    with get_engine_business().begin() as conn:
        frames = {}
        for table, csv_file in plan:
            try:
                frames[table] = prepare_table(conn, table, csv_file)
            except Exception as exc:
                print(f"ECHEC lors de la lecture de '{csv_file}' : {exc}")
                return 1

        problems = check_foreign_keys(conn, frames)
        if problems:
            print("Intégrité référentielle en défaut, rien n'a été inséré :")
            for problem in problems:
                print(f"  {problem}")
            return 1

        if not append:
            tables = ", ".join(table for table, _ in reversed(plan))
            conn.execute(text(f"TRUNCATE TABLE {tables} CASCADE"))
            print(f"Tables vidées : {tables}\n")

        for table, csv_file in plan:
            df = frames[table]
            try:
                df.to_sql(
                    table, conn, if_exists="append", index=False,
                    chunksize=500, method="multi",
                )
            except Exception as exc:
                # exc.orig est le message brut de PostgreSQL, sans la requête complète.
                print(f"ECHEC sur '{table}' : {getattr(exc, 'orig', exc)}")
                print("\nTransaction annulée, aucune donnée n'a été insérée.")
                return 1
            print(f"  {table:<10} {len(df):>4} lignes  <- {os.path.basename(csv_file)}")

    print("\nMigration terminée.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
