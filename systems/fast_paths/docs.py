"""Fast path Docs : rag_search hybride + une synthèse LLM."""

from systems.services import ask_question_with_sources


def answer_docs_question(question: str) -> str:
    """RAG direct avec sources citées en fin de réponse."""
    answer, sources = ask_question_with_sources(question)
    if sources:
        answer = f"{answer}\n\nSources : {', '.join(sources)}"
    return answer
