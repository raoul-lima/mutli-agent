"""Recherche hybride (pgvector + full-text search) dans la base RAG."""

import json
import os

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import text

from configs import get_embeddings, get_engine_rag, get_llm


def get_query_embedding(query_text: str):
    """Génère le vecteur d'embedding pour la question utilisateur."""
    return get_embeddings().embed_query(query_text)


def hybrid_search_postgres(query_text: str, top_k: int = 4):
    """Exécute une recherche hybride (pgvector + tsvector) dans PostgreSQL avec fusion RRF."""
    query_vector = get_query_embedding(query_text)
    vector_str = f"[{','.join(map(str, query_vector))}]"

    # Chaque CTE doit trier avant de limiter : sans ORDER BY au niveau du CTE,
    # PostgreSQL renvoie 20 lignes arbitraires puis les classe entre elles, ce
    # qui écarte les vrais meilleurs candidats.
    sql_query = text("""
        WITH vector_search AS (
            SELECT id, document, cmetadata,
                   ROW_NUMBER() OVER (ORDER BY embedding <=> :vector_str) AS rank_dense
            FROM langchain_pg_embedding
            ORDER BY embedding <=> :vector_str
            LIMIT 20
        ),
        text_search AS (
            SELECT id, document, cmetadata,
                   ROW_NUMBER() OVER (
                       ORDER BY ts_rank_cd(text_tsv, websearch_to_tsquery('french', :query_text)) DESC
                   ) AS rank_sparse
            FROM langchain_pg_embedding
            WHERE text_tsv @@ websearch_to_tsquery('french', :query_text)
            ORDER BY ts_rank_cd(text_tsv, websearch_to_tsquery('french', :query_text)) DESC
            LIMIT 20
        )
        SELECT
            COALESCE(v.id, t.id) AS id,
            COALESCE(v.document, t.document) AS document,
            COALESCE(v.cmetadata, t.cmetadata) AS cmetadata,
            (COALESCE(1.0 / (60 + v.rank_dense), 0.0) +
             COALESCE(1.0 / (60 + t.rank_sparse), 0.0)) AS rrf_score
        FROM vector_search v
        FULL OUTER JOIN text_search t ON v.id = t.id
        ORDER BY rrf_score DESC
        LIMIT :top_k;
    """)

    with get_engine_rag().connect() as conn:
        result = conn.execute(sql_query, {
            "vector_str": vector_str,
            "query_text": query_text,
            "top_k": top_k,
        })
        rows = result.fetchall()

    docs = []
    for row in rows:
        metadata = row.cmetadata if isinstance(row.cmetadata, dict) else json.loads(row.cmetadata or '{}')
        docs.append({
            "content": row.document,
            "metadata": metadata,
        })

    return docs


def format_source(metadata: dict) -> str:
    """« fichier.pdf — page 3 » à partir des métadonnées PGVector."""
    file_name = os.path.basename(metadata.get("source", "Document inconnu"))
    page_num = metadata.get("page", 0) + 1  # Conversion index 0 en numéro lisible
    return f"{file_name} — page {page_num}"


def ask_question_with_sources(question: str):
    """RAG direct (sans agent) : recherche hybride, réponse Gemini et sources."""
    relevant_docs = hybrid_search_postgres(question, top_k=4)

    if not relevant_docs:
        return "Aucun document pertinent n'a été trouvé.", []

    context_text = "\n\n".join(doc["content"] for doc in relevant_docs)

    sources = []
    for doc in relevant_docs:
        source_str = format_source(doc["metadata"])
        if source_str not in sources:
            sources.append(source_str)

    system_prompt = (
        "Vous êtes un assistant spécialisé dans les questions sur l'entreprise.\n"
        "Utilisez les éléments de contexte suivants pour répondre à la question.\n"
        "Si vous ne connaissez pas la réponse, dites simplement que vous ne savez pas.\n"
        "Répondez de manière concise et précise en français.\n\n"
        "Contexte :\n{context}"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{question}"),
    ])

    chain = prompt | get_llm() | StrOutputParser()
    answer = chain.invoke({"context": context_text, "question": question})

    return answer, sources
