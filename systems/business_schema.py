"""Schéma métier lu depuis PostgreSQL, formaté pour limiter les hallucinations de colonnes."""

from functools import lru_cache

from sqlalchemy import text

from configs import get_engine_business


@lru_cache(maxsize=1)
def business_schema() -> str:
    """Liste chaque colonne sur sa propre ligne — plus lisible pour le LLM qu'une seule ligne."""
    query = text(
        "SELECT table_name, column_name, data_type "
        "FROM information_schema.columns "
        "WHERE table_schema = 'public' "
        "ORDER BY table_name, ordinal_position"
    )
    try:
        with get_engine_business().connect() as conn:
            rows = conn.execute(query).fetchall()
    except Exception as exc:
        return (
            f"(Schéma indisponible : {exc}. Interrogez information_schema.columns "
            "pour découvrir les tables et colonnes avant d'écrire votre requête.)"
        )

    if not rows:
        return (
            "(Aucune table dans le schéma public : la base métier n'a pas été initialisée.)"
        )

    tables: dict[str, list[tuple[str, str]]] = {}
    for table_name, column_name, data_type in rows:
        tables.setdefault(table_name, []).append((column_name, data_type))

    lines: list[str] = [
        "Utilisez UNIQUEMENT les noms de colonnes ci-dessous — ne devinez jamais "
        "nom, prenom, nom_client ou montant_total."
    ]
    for name, columns in tables.items():
        lines.append(f"\nTable `{name}` :")
        for column_name, data_type in columns:
            lines.append(f"  - {column_name} ({data_type})")
    return "\n".join(lines)
