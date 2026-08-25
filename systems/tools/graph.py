from langchain_core.tools import tool
from langchain_neo4j import GraphCypherQAChain

from configs import get_graph, get_llm


@tool
def graph_rag(query: str) -> str:
    """Interroge le knowledge graph Neo4j sur les relations entre entités.

    Traduit la question en Cypher puis renvoie la réponse en langage naturel.
    Utile pour les dépendances, hiérarchies et liens entre entités des documents.
    """
    try:
        chain = GraphCypherQAChain.from_llm(
            llm=get_llm(),
            graph=get_graph(),
            verbose=True,
            allow_dangerous_requests=True,
        )
        response = chain.invoke({"query": query})
        return response["result"]
    except Exception as e:
        return f"Erreur lors de l'interrogation du graphe Neo4j : {str(e)}"
