from langchain_core.tools import tool

from systems.services import format_source, hybrid_search_postgres


@tool
def rag_search(query: str) -> str:
    """Recherche dans les documents PDF internes (RH, CGV, procédures, stock, sécurité).

    Renvoie les extraits les plus pertinents, chacun préfixé de son fichier et de sa page.
    """
    docs = hybrid_search_postgres(query, top_k=4)
    if not docs:
        return "Aucun document PDF pertinent n'a été trouvé."
    return "\n\n---\n\n".join(
        f"[Source: {format_source(d['metadata'])}]\n{d['content']}" for d in docs
    )
