"""Agent Graphe : spécialiste des relations entre entités."""

from systems.agents.base import subagent_tool
from systems.tools import graph_rag

PROMPT = """Vous êtes le spécialiste du knowledge graph de Grossiste Mada, \
construit par extraction d'entités et de relations depuis les documents internes.

Vous recevez une question autonome portant sur des relations, des dépendances ou des \
hiérarchies entre entités, et vous y répondez uniquement à partir de `graph_rag`.

- Si la réponse est vide, reformulez en nommant explicitement les entités concernées \
puis réessayez une fois.
- Décrivez les relations trouvées, en nommant les entités aux deux extrémités.
- Si le graphe ne contient pas l'information, dites-le : il ne couvre que ce qui a été \
extrait des PDF, et l'extraction est imparfaite.

Vous n'avez accès ni aux documents en texte intégral ni à la base de données : ne \
produisez aucun chiffre métier."""

DESCRIPTION = """Interroge le spécialiste du knowledge graph pour les relations, \
dépendances et hiérarchies entre entités extraites des documents internes. À utiliser \
pour « qu'est-ce qui est lié à X », « quelle est la chaîne d'impact si Y », et non pour \
un chiffre ou le texte d'une règle.

Envoyez une question autonome et complète, sans référence à la conversation en cours. \
Peut être appelé en parallèle, dans le même tour, avec `ask_docs_agent` ou \
`ask_sql_agent` lorsque les sous-questions sont indépendantes."""

ask_graph_agent = subagent_tool(
    name="ask_graph_agent",
    description=DESCRIPTION,
    prompt=PROMPT,
    tools=[graph_rag],
)
