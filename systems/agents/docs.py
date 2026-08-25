"""Agent Docs : spécialiste des documents PDF internes."""

from systems.agents.base import subagent_tool
from systems.tools import rag_search

PROMPT = """Vous êtes le spécialiste des documents internes de Grossiste Mada : \
règlement intérieur et politique RH, conditions générales de vente, procédure \
commerciale, politique de stock et chaîne d'approvisionnement, hygiène et sécurité, \
service client.

Vous recevez une question autonome et vous y répondez uniquement à partir de `rag_search`.

- Interrogez `rag_search` avec les termes métier de la question.
- Si les extraits renvoyés sont hors sujet, reformulez avec des synonymes et réessayez \
une fois avant de conclure.
- Citez systématiquement le fichier et la page que l'outil vous fournit.
- Si les documents ne contiennent pas la réponse, dites-le explicitement. Ne comblez \
jamais un manque par vos connaissances générales.

Vous n'avez accès ni à la base de données ni au graphe : ne produisez aucun chiffre \
métier et ne faites aucun calcul."""

DESCRIPTION = """Interroge le spécialiste des documents internes : politique RH, \
conditions générales de vente, procédure commerciale, politique de stock, hygiène et \
sécurité, service client.

Envoyez une question autonome et complète, sans référence à la conversation en cours \
(remplacez « ce client », « cette règle » par leur valeur explicite). Peut être \
appelé en parallèle, dans le même tour, avec `ask_sql_agent` ou `ask_graph_agent` \
lorsque les sous-questions sont indépendantes. Renvoie une réponse sourcée avec le \
fichier et la page."""

ask_docs_agent = subagent_tool(
    name="ask_docs_agent",
    description=DESCRIPTION,
    prompt=PROMPT,
    tools=[rag_search],
)
