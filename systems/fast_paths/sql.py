"""Fast path SQL : text-to-SQL en un shot + formatage, sans boucle ReAct."""

from datetime import date

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from configs import get_llm
from systems.business_schema import business_schema
from systems.schema_hints import SQL_BUSINESS_HINTS
from systems.tools.sql import sql_database

_GENERATE_SQL = ChatPromptTemplate.from_messages([
    (
        "system",
        """Vous écrivez une seule requête PostgreSQL SELECT pour répondre à la question.

Date du jour : {today}.

Schéma :
{schema}

{hints}

Règles :
- Un seul SELECT, rien d'autre.
- Chaque colonne du SQL doit apparaître **à l'identique** dans le schéma ci-dessus.
- Pour « ce mois-ci », filtrez depuis le premier jour du mois courant ({today}).
- Ne générez pas de requête de vérification : répondez directement à la question.
- Répondez uniquement avec le SQL, sans markdown ni explication.""",
    ),
    ("human", "{question}"),
])

_FIX_SQL = ChatPromptTemplate.from_messages([
    (
        "system",
        """Corrigez la requête SELECT suivante. Schéma :
{schema}

{hints}

Règles :
- Chaque colonne doit exister dans le schéma avec le même nom (pas de nom, prenom, nom_client, montant_total).
- Répondez uniquement avec le SQL corrigé.""",
    ),
    (
        "human",
        "Question : {question}\n\nRequête erronée :\n{bad_sql}\n\nErreur :\n{error}",
    ),
])

_FORMAT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Répondez en français, concis, avec les chiffres du résultat SQL. "
        "Précisez la période ou le périmètre si pertinent.",
    ),
    ("human", "Question : {question}\n\nRésultat SQL :\n{result}"),
])


def _generate_select(question: str, *, bad_sql: str = "", error: str = "") -> str:
    llm = get_llm() | StrOutputParser()
    if bad_sql:
        raw = (_FIX_SQL | llm).invoke({
            "schema": business_schema(),
            "hints": SQL_BUSINESS_HINTS,
            "question": question,
            "bad_sql": bad_sql,
            "error": error,
        })
    else:
        raw = (_GENERATE_SQL | llm).invoke({
            "today": date.today().isoformat(),
            "schema": business_schema(),
            "hints": SQL_BUSINESS_HINTS,
            "question": question,
        })
    sql = raw.strip().removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
    return sql


def answer_sql_question(question: str) -> str:
    """Deux appels LLM max : génération SQL (+ correction si besoin) puis formatage."""
    sql = _generate_select(question)
    result = sql_database.invoke({"query": sql})

    if result.startswith("Erreur"):
        sql = _generate_select(question, bad_sql=sql, error=result)
        result = sql_database.invoke({"query": sql})
        if result.startswith("Erreur"):
            raise RuntimeError(result)

    llm = get_llm() | StrOutputParser()
    return (_FORMAT | llm).invoke({"question": question, "result": result})
