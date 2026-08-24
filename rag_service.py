import os
import json
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

DB_URL = os.getenv("DB_URL", "postgresql+psycopg2://postgres:admin@localhost:5432/grossiste_mada")
COLLECTION_NAME = "documents_entreprise"

engine = create_engine(DB_URL)

def get_query_embedding(query_text: str):
    """Génère le vecteur d'embedding pour la question utilisateur."""
    api_key = os.getenv("GOOGLE_API_KEY")
    embeddings = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-2",
        google_api_key=api_key
    )
    return embeddings.embed_query(query_text)

def hybrid_search_postgres(query_text: str, top_k: int = 3):
    """Exécute une recherche hybride (pgvector + tsvector) dans PostgreSQL avec fusion RRF."""
    query_vector = get_query_embedding(query_text)
    vector_str = f"[{','.join(map(str, query_vector))}]"

    # Requête SQL hybride avec RRF (Reciprocal Rank Fusion)
    sql_query = text("""
        WITH vector_search AS (
            SELECT id, document, cmetadata,
                   ROW_NUMBER() OVER (ORDER BY embedding <=> :vector_str) AS rank_dense
            FROM langchain_pg_embedding
            LIMIT 20
        ),
        text_search AS (
            SELECT id, document, cmetadata,
                   ROW_NUMBER() OVER (
                       ORDER BY ts_rank_cd(text_tsv, websearch_to_tsquery('french', :query_text)) DESC
                   ) AS rank_sparse
            FROM langchain_pg_embedding
            WHERE text_tsv @@ websearch_to_tsquery('french', :query_text)
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

    with engine.connect() as conn:
        result = conn.execute(sql_query, {
            "vector_str": vector_str,
            "query_text": query_text,
            "top_k": top_k
        })
        rows = result.fetchall()

    docs = []
    for row in rows:
        metadata = row.cmetadata if isinstance(row.cmetadata, dict) else json.loads(row.cmetadata or '{}')
        docs.append({
            "content": row.document,
            "metadata": metadata
        })

    return docs

def ask_question_with_sources(question: str):
    """Effectue la recherche hybride native SQL, interroge Gemini et retourne la réponse + sources."""
    api_key = os.getenv("GOOGLE_API_KEY")
    
    # 1. Recherche hybride dans PostgreSQL
    relevant_docs = hybrid_search_postgres(question, top_k=3)

    if not relevant_docs:
        return "Aucun document pertinent n'a été trouvé.", []

    # 2. Contexte pour le LLM
    context_text = "\n\n".join(doc["content"] for doc in relevant_docs)

    # 3. Extraction des sources avec nom du fichier et numéro de page
    sources = []
    for doc in relevant_docs:
        source_path = doc["metadata"].get("source", "Document inconnu")
        file_name = os.path.basename(source_path)
        page_num = doc["metadata"].get("page", 0) + 1  # Conversion index 0 en numéro de page lisible
        
        source_str = f"{file_name} — page {page_num}"
        if source_str not in sources:
            sources.append(source_str)

    # 4. Inférence avec Gemini 1.5 Flash
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite",
        temperature=0,
        google_api_key=api_key
    )

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

    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke({"context": context_text, "question": question})

    return answer, sources