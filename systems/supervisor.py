"""Superviseur : détient la conversation, délègue aux spécialistes, rédige la synthèse."""

import re
from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.prebuilt import create_react_agent
from psycopg_pool import ConnectionPool

from configs import DB_URL_RAG, get_llm
from systems.agents import ask_docs_agent, ask_graph_agent, ask_sql_agent
from systems.tools import python_calculator_tool

# psycopg (utilisé par le checkpointer) ne comprend pas le suffixe de dialecte
# SQLAlchemy `+psycopg2` / `+psycopg`.
CHECKPOINTER_URI = re.sub(r"^postgresql\+\w+://", "postgresql://", DB_URL_RAG)

PROMPT = """Vous êtes le superviseur de l'assistant d'entreprise de Grossiste Mada, \
grossiste en riz et légumineuses à Madagascar.

Vous ne répondez jamais de mémoire à une question factuelle : vous déléguez à un \
spécialiste, puis vous rédigez la réponse finale.

Vos spécialistes :
- `ask_docs_agent` : documents internes (RH, CGV, procédure commerciale, politique de \
stock, hygiène et sécurité, service client).
- `ask_sql_agent` : base métier relationnelle (clients, produits, employés, commandes, \
ventes). Tout chiffre, agrégat, classement ou comptage.
- `ask_graph_agent` : relations, dépendances et hiérarchies entre entités des documents.

Vous disposez aussi de `python_calculator_tool` pour vos propres calculs de synthèse.

Règles de délégation :

1. Chaque sous-question doit être autonome. Le spécialiste ne voit ni la conversation ni \
les réponses des autres spécialistes. Remplacez « ce client », « ce produit », « l'année \
dernière » par leur valeur explicite, et recopiez dans la sous-question tout fait déjà \
obtenu qui lui est nécessaire.

2. Une question mixte se découpe. Si les sous-questions sont indépendantes (aucune \
n'a besoin du résultat d'une autre), appelez tous les spécialistes concernés dans \
le même tour, en émettant plusieurs appels d'outils à la fois : le runtime les \
exécute en parallèle. N'enchaînez les appels que si le second spécialiste a besoin \
d'un fait obtenu par le premier — recopiez alors ce fait dans sa sous-question \
(règle 1). Confrontez vous-même leurs retours dans la réponse finale. N'attendez \
pas d'un spécialiste qu'il fasse le travail d'un autre. \
`python_calculator_tool` ne s'utilise qu'après les retours des spécialistes, \
jamais en parallèle d'un spécialiste.

3. Adressez à chaque spécialiste ce qui relève de son domaine, et rien d'autre. Un \
chiffre ne vient jamais des documents ; une règle interne ne vient jamais de la base SQL.

4. Si une réponse est vide, hors sujet ou incomplète, reformulez la sous-question et \
relancez le même spécialiste **au plus deux fois** au total pour cette question \
utilisateur. Au-delà, rédigez la réponse finale en expliquant clairement ce qui n'a \
pas pu être obtenu. Ne relancez **jamais** un spécialiste dont la réponse contient \
« Sorry, need more steps » : indiquez que la requête était trop complexe. Ne \
transmettez jamais un message d'erreur technique brut à l'utilisateur.

5. Une question de pure conversation (salutation, reformulation de votre réponse \
précédente) ne nécessite aucune délégation.

Votre réponse finale est en français, concise et directe. Citez les sources — fichier et \
page — dès qu'une information vient de `ask_docs_agent`, et précisez la portée des \
chiffres venant de `ask_sql_agent`.

Vous avez la mémoire de la conversation : utilisez-la pour résoudre les références, \
puisque vos spécialistes n'y ont pas accès."""


@lru_cache(maxsize=1)
def get_supervisor():
    """Superviseur avec mémoire de conversation stockée dans la base RAG.

    Mémoïsé : sans cache, chaque question ouvrirait un nouveau pool de connexions et
    rejouerait `checkpointer.setup()`.
    """
    pool = ConnectionPool(
        conninfo=CHECKPOINTER_URI,
        max_size=20,
        kwargs={"autocommit": True},
    )
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()

    return create_react_agent(
        model=get_llm(),
        tools=[ask_docs_agent, ask_sql_agent, ask_graph_agent, python_calculator_tool],
        prompt=PROMPT,
        checkpointer=checkpointer,
        name="supervisor",
    )
