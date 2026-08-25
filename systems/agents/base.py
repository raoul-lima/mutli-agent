"""Fabrique commune aux sous-agents : un agent ReAct emballé en outil du superviseur."""

from collections.abc import Callable, Sequence
from functools import lru_cache

from langchain_core.tools import BaseTool, StructuredTool
from langgraph.errors import GraphRecursionError
from langgraph.prebuilt import create_react_agent

from configs import get_llm
from systems.messages import extract_text

# Une boucle d'auto-correction qui n'aboutit pas doit rendre la main au superviseur
# plutôt que de tourner. Compté en super-étapes LangGraph, soit environ cinq
# allers-retours modèle/outil.
SUBAGENT_RECURSION_LIMIT = 12


def subagent_tool(
    *,
    name: str,
    description: str,
    prompt: str | Callable[[], str],
    tools: Sequence[BaseTool],
) -> StructuredTool:
    """Expose un sous-agent ReAct comme un outil à paramètre unique.

    La signature `question: str` est le contrat d'isolation : le sous-agent ne reçoit
    que ce texte, jamais l'historique de conversation du superviseur.

    `prompt` accepte un appelable pour les agents dont le prompt dépend d'une source
    externe (l'agent SQL lit le schéma en base) : rien n'est évalué à l'import.

    `coroutine` permet au ToolNode LangGraph d'exécuter plusieurs spécialistes
    via `asyncio.gather` lorsque le graphe tourne en async ; le chemin sync utilise
    un pool de threads.
    """

    @lru_cache(maxsize=1)
    def build():
        resolved_prompt = prompt() if callable(prompt) else prompt
        return create_react_agent(
            model=get_llm(),
            tools=list(tools),
            prompt=resolved_prompt,
            name=name,
        )

    def _answer_from_result(result) -> str:
        return extract_text(result["messages"][-1].content)

    def _answer_from_error(exc: BaseException) -> str:
        if isinstance(exc, GraphRecursionError):
            return (
                f"Le spécialiste {name} n'a pas convergé sur cette question. "
                "Reformulez-la de façon plus précise ou découpez-la."
            )
        # Le superviseur doit pouvoir reformuler ou l'expliquer à l'utilisateur ;
        # une exception qui remonte ferait échouer toute la conversation.
        return f"Le spécialiste {name} est indisponible : {exc}"

    def run(question: str) -> str:
        try:
            result = build().invoke(
                {"messages": [("user", question)]},
                config={"recursion_limit": SUBAGENT_RECURSION_LIMIT},
            )
        except Exception as exc:
            return _answer_from_error(exc)
        return _answer_from_result(result)

    async def arun(question: str) -> str:
        try:
            result = await build().ainvoke(
                {"messages": [("user", question)]},
                config={"recursion_limit": SUBAGENT_RECURSION_LIMIT},
            )
        except Exception as exc:
            return _answer_from_error(exc)
        return _answer_from_result(result)

    return StructuredTool.from_function(
        func=run,
        coroutine=arun,
        name=name,
        description=description,
    )
