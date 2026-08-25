"""Routeur léger : heuristiques puis un appel LLM structuré si nécessaire."""

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from configs import get_llm

RouteKind = Literal["docs", "sql", "graph", "mixed", "chat"]

_CHAT_RE = re.compile(
    r"^(bonjour|salut|bonsoir|merci|ok|d'accord|au revoir)\b",
    re.IGNORECASE,
)
_REFERENTIAL_RE = re.compile(
    r"\b(ce client|ce produit|cette règle|celui-ci|celle-ci|"
    r"et pour (lui|elle|ce|cette)|comme avant|ta réponse)\b",
    re.IGNORECASE,
)
_SQL_RE = re.compile(
    r"\b(combien|nombre|total|liste|classement|moyenne|"
    r"commandes?|clients?|ventes?|employés?|chiffre|statistique)\b",
    re.IGNORECASE,
)
_DOCS_RE = re.compile(
    r"\b(politique|règle|procédure|cgv|conditions|congés?|"
    r"remboursement|reboursement|hygiène|sécurité|stock|rh|document)\b",
    re.IGNORECASE,
)
_GRAPH_RE = re.compile(
    r"\b(lié|liée|liés|liées|relation|relations|dépend|dépendance|"
    r"hiérarchie|chaîne d'impact|entités? liées)\b",
    re.IGNORECASE,
)

ROUTER_SYSTEM = """Vous classifiez les questions pour l'assistant Grossiste Mada.

Date du jour : {today}.

Routes possibles :
- docs : une seule source documentaire (RH, CGV, procédures, politiques). Pas de chiffre métier.
- sql : chiffres, comptages, listes ou agrégats depuis la base clients/commandes/ventes.
- graph : relations ou dépendances entre entités extraites des documents.
- mixed : au moins deux sources (ex. règle + chiffre, document + base, ou deux domaines distincts).
- chat : salutation, remerciement, ou suivi conversationnel avec référence implicite au tour précédent.

Règles :
- Résolvez « ce mois-ci », « l'année dernière », « ce client » en valeur explicite dans `question`.
- Une question purement chiffrée → sql. Purement documentaire → docs. Purement relationnelle → graph.
- Dès qu'il faut confronte règle et chiffre, ou deux spécialistes → mixed.
- Si la question suppose la mémoire de la conversation sans donner tous les faits → chat.

`question` doit être autonome et prête à être transmise à un spécialiste."""


class RouteDecision(BaseModel):
    route: RouteKind
    question: str = Field(description="Question autonome, références résolues si possible.")


def heuristic_route(question: str) -> RouteDecision | None:
    """Routage instantané sans LLM pour les cas évidents ; None si ambigu."""
    text = question.strip()
    if not text:
        return RouteDecision(route="chat", question=text)

    if _CHAT_RE.match(text) and len(text.split()) <= 6:
        return RouteDecision(route="chat", question=text)

    if _REFERENTIAL_RE.search(text):
        return RouteDecision(route="chat", question=text)

    has_sql = bool(_SQL_RE.search(text))
    has_docs = bool(_DOCS_RE.search(text))
    has_graph = bool(_GRAPH_RE.search(text))

    # « entités liées à la politique X » : le mot politique nomme l'entité, pas une question doc.
    if has_graph and not has_sql:
        return RouteDecision(route="graph", question=text)

    sources = sum([has_sql, has_docs, has_graph])
    if sources >= 2:
        return RouteDecision(route="mixed", question=text)

    if has_sql and not has_docs and not has_graph:
        return RouteDecision(route="sql", question=text)

    if has_docs and not has_sql and not has_graph:
        return RouteDecision(route="docs", question=text)

    return None


def uses_mixed_fast_path(decision: RouteDecision, question: str) -> bool:
    """Fast path mixte docs+sql uniquement ; le graphe ou le chat restent au superviseur."""
    if decision.route != "mixed":
        return False
    return not bool(_GRAPH_RE.search(question))


def route_question(question: str) -> RouteDecision:
    """Heuristique d'abord, sinon un seul appel LLM structuré."""
    fast = heuristic_route(question)
    if fast is not None:
        return fast

    router = get_llm().with_structured_output(RouteDecision)
    return router.invoke(
        [
            ("system", ROUTER_SYSTEM.format(today=date.today().isoformat())),
            ("human", question),
        ]
    )
