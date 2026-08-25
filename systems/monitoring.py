"""État du tracing LangSmith.

LangSmith s'active par variables d'environnement : `langchain` et `langgraph`
instrumentent automatiquement chaque appel, sans callback à câbler. Le revers est
qu'un tracing inactif ne se remarque pas — d'où cette fonction, dont l'interface
affiche le résultat.
"""

import os

# Charge `.env` avant de lire LANGSMITH_* : app.py appelle tracing_status()
# avant d'importer le runner, donc configs.py n'a pas encore tourné.
import configs  # noqa: F401


def tracing_status() -> tuple[bool, str]:
    """Renvoie (tracing actif, libellé lisible) pour affichage dans l'interface."""
    from langsmith.utils import tracing_is_enabled

    if not tracing_is_enabled():
        return False, "Tracing LangSmith inactif (`LANGSMITH_TRACING` non défini à `true`)"

    if not (os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")):
        return False, "`LANGSMITH_TRACING` activé mais `LANGSMITH_API_KEY` manquante"

    project = (
        os.getenv("LANGSMITH_PROJECT")
        or os.getenv("LANGCHAIN_PROJECT")
        or "default"
    )
    return True, f"Tracing LangSmith actif — projet `{project}`"
