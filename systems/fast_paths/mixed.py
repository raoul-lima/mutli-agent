"""Fast path mixte : découpage, docs + SQL en parallèle, synthèse en un LLM."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from configs import get_llm
from systems.fast_paths.docs import answer_docs_question
from systems.fast_paths.sql import answer_sql_question

_SPLIT = ChatPromptTemplate.from_messages([
    (
        "system",
        """Vous découpez une question mixte Grossiste Mada en deux sous-questions \
autonomes. Date du jour : {today}.

- `docs_question` : règles, politiques, procédures (remboursement, CGV, RH…). Aucun chiffre \
métier à produire.
- `sql_question` : clients, commandes, comptages, listes depuis la base. Aucune règle \
interne à citer.

Résolvez les références (« ce produit », « récemment », « en cours ») en valeurs \
explicites dans chaque sous-question.""",
    ),
    ("human", "{question}"),
])

_SYNTHESIZE = ChatPromptTemplate.from_messages([
    (
        "system",
        """Vous synthétisez une réponse finale en français pour Grossiste Mada.
Confrontez la règle documentaire et les chiffres SQL. Citez fichier/page pour la \
partie documentaire. Si une source n'a pas répondu, dites-le clairement — ne \
inventez rien et ne concluez pas par une formule de politesse sans contenu.""",
    ),
    (
        "human",
        "Question : {question}\n\n"
        "Documents :\n{docs_answer}\n\n"
        "Base métier :\n{sql_answer}",
    ),
])


class MixedSplit(BaseModel):
    docs_question: str = Field(description="Sous-question documentaire autonome.")
    sql_question: str = Field(description="Sous-question chiffrée autonome.")


def split_mixed_question(question: str) -> MixedSplit:
    chain = _SPLIT | get_llm().with_structured_output(MixedSplit)
    return chain.invoke({"question": question, "today": date.today().isoformat()})


def answer_mixed_question(question: str) -> str:
    """Split → fast_docs ∥ fast_sql → synthèse (~4–6 appels LLM)."""
    split = split_mixed_question(question)
    with ThreadPoolExecutor(max_workers=2) as pool:
        docs_future = pool.submit(answer_docs_question, split.docs_question)
        sql_future = pool.submit(answer_sql_question, split.sql_question)
        docs_answer = docs_future.result()
        sql_answer = sql_future.result()

    llm = get_llm() | StrOutputParser()
    return (_SYNTHESIZE | llm).invoke({
        "question": question,
        "docs_answer": docs_answer,
        "sql_answer": sql_answer,
    })
