"""Point d'entrée applicatif : routeur hybride puis fast path ou superviseur."""

from systems.fast_paths.docs import answer_docs_question
from systems.fast_paths.graph import answer_graph_question
from systems.fast_paths.mixed import answer_mixed_question
from systems.fast_paths.sql import answer_sql_question
from systems.messages import extract_text
from systems.router import RouteDecision, route_question, uses_mixed_fast_path
from systems.supervisor import get_supervisor


def _try_fast_path(decision: RouteDecision, question: str) -> tuple[str, list[str]] | None:
    """Dispatch fast path ; résolution au runtime pour permettre le mock en tests."""
    if decision.route == "mixed" and uses_mixed_fast_path(decision, question):
        return answer_mixed_question(question), ["fast_mixed"]
    if decision.route == "docs":
        return answer_docs_question(decision.question), ["fast_docs"]
    if decision.route == "sql":
        return answer_sql_question(decision.question), ["fast_sql"]
    if decision.route == "graph":
        return answer_graph_question(decision.question), ["fast_graph"]
    return None


def run_supervisor(question: str, thread_id: str = "default_session"):
    """Superviseur complet avec mémoire PostgreSQL (questions mixtes ou suivi)."""
    supervisor = get_supervisor()
    config = {
        "configurable": {"thread_id": thread_id},
        "run_name": "supervisor",
        "metadata": {"thread_id": thread_id},
        "tags": ["grossiste-mada", "supervisor"],
    }
    response = supervisor.invoke({"messages": [("user", question)]}, config=config)
    final_message = extract_text(response["messages"][-1].content)
    tool_calls = [
        tc["name"]
        for msg in response["messages"]
        for tc in getattr(msg, "tool_calls", None) or []
    ]
    return final_message, tool_calls


def run_agent(question: str, thread_id: str = "default_session"):
    """Routeur → fast path ou superviseur (mixed complexe, chat, fallback).

    LangSmith : tags `fast-*` ou `supervisor`. Pas de callback supplémentaire.
    """
    decision = route_question(question)

    try:
        fast = _try_fast_path(decision, question)
        if fast is not None:
            return fast
    except Exception:
        pass

    return run_supervisor(question, thread_id=thread_id)
