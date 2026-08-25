"""Agent SQL : spécialiste de la base métier relationnelle."""

from systems.agents.base import subagent_tool
from systems.business_schema import business_schema
from systems.schema_hints import SQL_BUSINESS_HINTS
from systems.tools import python_calculator_tool, sql_database


def build_prompt() -> str:
    return f"""Vous êtes le spécialiste de la base métier PostgreSQL de Grossiste Mada.

Vous recevez une question autonome et vous y répondez uniquement à partir de \
`sql_database`.

Schéma disponible :
{business_schema()}

{SQL_BUSINESS_HINTS}

- Écrivez une requête SELECT, exécutez-la, puis lisez le résultat. Seul SELECT est \
autorisé.
- Avant d'écrire du SQL, vérifiez que chaque colonne utilisée apparaît dans le schéma \
ci-dessus avec le même nom.
- Si l'outil renvoie une erreur « column … does not exist », relisez le schéma et \
corrigez — ne devinez pas un synonyme (`nom_client`, `montant_total`…).
- Utilisez `python_calculator_tool` pour les moyennes, ratios et pourcentages plutôt que \
de calculer de tête.
- Répondez avec les chiffres obtenus en précisant sur quoi ils portent et sur quelle \
période. Si la requête ne renvoie rien, dites-le.

Vous n'avez accès ni aux documents ni au graphe : ne citez aucune règle interne."""


DESCRIPTION = """Interroge le spécialiste de la base métier (clients, produits, \
employés, commandes, ventes) pour tout chiffre, agrégat, classement ou comptage.

Envoyez une question autonome et complète, sans référence à la conversation en cours \
(remplacez « ce client », « l'année dernière » par leur valeur explicite). Peut être \
appelé en parallèle, dans le même tour, avec `ask_docs_agent` ou `ask_graph_agent` \
lorsque les sous-questions sont indépendantes. Renvoie les chiffres obtenus, pas de \
règle interne."""

ask_sql_agent = subagent_tool(
    name="ask_sql_agent",
    description=DESCRIPTION,
    prompt=build_prompt,
    tools=[sql_database, python_calculator_tool],
)
