"""Fast path Graphe : graph_rag direct, sans superviseur ni sous-agent."""

from systems.tools.graph import graph_rag


def answer_graph_question(question: str) -> str:
    return graph_rag.invoke({"query": question})
