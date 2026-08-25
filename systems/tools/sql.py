import json

from langchain_core.tools import tool
from sqlalchemy import text

from configs import get_engine_business
from systems.schema_hints import SQL_COLUMN_GLOSSARY


@tool
def sql_database(query: str) -> str:
    """Exécute une requête SELECT sur la base métier et renvoie les lignes en JSON.

    Seul SELECT est autorisé. En cas d'erreur, le message brut de PostgreSQL est
    renvoyé afin que l'appelant puisse corriger sa requête.
    """
    if not query.strip().upper().startswith("SELECT"):
        return "Erreur : Seules les requêtes SELECT sont autorisées."
    try:
        with get_engine_business().connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
            keys = result.keys()
            if not rows:
                return "Aucun résultat trouvé dans la base métier."
            data = [dict(zip(keys, row)) for row in rows]
            return json.dumps(data, default=str, ensure_ascii=False)
    except Exception as e:
        msg = f"Erreur SQL Métier : {str(e)}"
        if "does not exist" in str(e).lower():
            msg += (
                "\n\nColonne absente du schéma : relisez la liste des colonnes. "
                f"Rappel — {SQL_COLUMN_GLOSSARY.strip()}"
            )
        return msg
