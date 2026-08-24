import os
import json
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# LangGraph & Checkpointer
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_experimental.utilities import PythonREPL
from langfuse.langchain import CallbackHandler
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain

load_dotenv()

# ==========================================
# CONNEXIONS DISTINCTES
# ==========================================

# 1. Base RAG & Checkpointer (Port 5433)
RAG_URL = os.getenv("DB_RAG_URL", "postgresql+psycopg2://postgres:admin@db:5432/grossiste_mada")
RAG_URI = RAG_URL.replace("postgresql+psycopg2://", "postgresql://")
engine_rag = create_engine(RAG_URL)
pool_checkpointer = ConnectionPool(conninfo=RAG_URI, max_size=20, kwargs={"autocommit": True})

# 2. Base Métier (Port 5432)
BUSINESS_URL = os.getenv("DB_BUSINESS_URL", "postgresql+psycopg2://postgres:admin@host.docker.internal:5432/grossiste_mada")
engine_business = create_engine(BUSINESS_URL)

# Initialisation de la connexion Neo4j
neo4j_graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
    username=os.getenv("NEO4J_USERNAME", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "password123")
)
# ==========================================
# OUTILS DE L'AGENT
# ==========================================

@tool
def graph_rag_tool(query: str) -> str:
    """
    Utile pour analyser la hiérarchie, les dépendances et les relations complexes entre entités.
    Permet de répondre à des questions telles que :
    - Quelles sont les entités liées à tel contrat ?
    - Quelle est la hiérarchie d'impact si la catégorie X subit un retard ?
    """
    try:
        chain = GraphCypherQAChain.from_llm(
            llm=ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", temperature=0, google_api_key=os.getenv("GOOGLE_API_KEY")),
            graph=neo4j_graph,
            verbose=True,
            allow_dangerous_requests=True
        )
        response = chain.invoke({"query": query})
        return response["result"]
    except Exception as e:
        return f"Erreur lors de l'interrogation du graphe Neo4j : {str(e)}"

@tool
def rag_search_tool(query: str) -> str:
    """Interroge la base RAG (PDF, contrats, RH) sur le port 5433."""
    from rag_service import hybrid_search_postgres
    docs = hybrid_search_postgres(query, top_k=3)
    if not docs:
        return "Aucun document PDF pertinent n'a été trouvé."
    results = []
    for d in docs:
        source_path = d["metadata"].get("source", "Inconnu")
        file_name = os.path.basename(source_path)
        page = d["metadata"].get("page", 0) + 1
        results.append(f"[Source: {file_name} - Page {page}]\n{d['content']}")
    return "\n\n---\n\n".join(results)

@tool
def sql_database_tool(query: str) -> str:
    """Interroge la base Métier (customers, orders, products, employees, sales) sur le port 5432."""
    if not query.strip().upper().startswith("SELECT"):
        return "Erreur : Seules les requêtes SELECT sont autorisées."
    try:
        # Exécution explicite sur engine_business
        with engine_business.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
            keys = result.keys()
            if not rows:
                return "Aucun résultat trouvé dans la base métier."
            data = [dict(zip(keys, row)) for row in rows]
            return json.dumps(data, default=str, ensure_ascii=False)
    except Exception as e:
        return f"Erreur SQL Métier : {str(e)}"

python_repl = PythonREPL()

@tool
def python_calculator_tool(code: str) -> str:
    """Exécute du code Python pour faire des calculs ou statistiques."""
    try:
        result = python_repl.run(code)
        return f"Résultat Python :\n{result}"
    except Exception as e:
        return f"Erreur Python : {str(e)}"

# ==========================================
# AGENT & MEMOIRE
# ==========================================

def get_agent_executor():
    api_key = os.getenv("GOOGLE_API_KEY")
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite",
        temperature=0,
        google_api_key=api_key
    )

    tools = [rag_search_tool, sql_database_tool, python_calculator_tool, graph_rag_tool]

    system_prompt = (
        "Vous êtes un assistant IA d'entreprise pour Grossiste Mada.\n"
        "Vous disposez de 3 outils spécialisés :\n"
        "- `rag_search_tool` (Port 5433) : Pour les documents PDF et règles internes.\n"
        "- `sql_database_tool` (Port 5432) : Pour les données relationnelles (customers, orders, products, employees, sales).\n"
        "- `python_calculator_tool` : Pour les calculs complexes.\n"
        "Vous avez de la mémoire grâce à LangGraph : réutilisez le contexte des messages précédents."
    )

    # Checkpointer stocké explicitement dans la base RAG (5433)
    checkpointer = PostgresSaver(pool_checkpointer)
    checkpointer.setup()

    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
        checkpointer=checkpointer
    )

def run_agent(question: str, thread_id: str = "default_session"):
    agent_executor = get_agent_executor()
    langfuse_handler = CallbackHandler()

    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": [langfuse_handler]
    }
    
    response = agent_executor.invoke({"messages": [("user", question)]}, config=config)
    
    last_message = response["messages"][-1]
    raw_content = last_message.content
    
    if isinstance(raw_content, list):
        text_parts = []
        for block in raw_content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)
        final_message = "\n".join(text_parts)
    else:
        final_message = str(raw_content)
    
    tool_calls = []
    for msg in response["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(tc["name"])
                
    return final_message, tool_calls