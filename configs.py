"""Configuration partagée par l'application, les outils et les scripts d'ingestion."""

import os
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent

# Chemins absolus : les scripts d'ingestion sont lancés depuis des répertoires
# variés (hôte, conteneur), un chemin relatif au CWD casse selon l'appelant.
PATH_DOCS = str(PROJECT_ROOT / "docs" / "files_entreprise")
PATH_CSV = str(PROJECT_ROOT / "docs" / "csv_files")

MODEL_GEMINI = "gemini-3.5-flash-lite"
MODEL_EMBEDDING = "gemini-embedding-2"
COLLECTION_NAME = "documents_entreprise"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


def _normalize_driver(url: str) -> str:
    """Force le driver psycopg3, seul accepté par langchain_postgres.PGVector.

    Tout le projet partage donc une seule forme d'URL, quel que soit le driver
    présent dans la variable d'environnement.
    """
    return re.sub(r"^postgresql(\+\w+)?://", "postgresql+psycopg://", url)


def _postgres_url(env_var: str, database: str) -> str:
    """URL SQLAlchemy vers une base du container `db`.

    docker-compose injecte l'URL complète (hôte interne `db`) ; hors conteneur
    on la reconstruit depuis les variables POSTGRES_* vers localhost.
    """
    url = os.getenv(env_var)
    if url:
        return _normalize_driver(url)

    user = os.getenv("POSTGRES_USER", "postgres")
    password = quote_plus(os.getenv("POSTGRES_PASSWORD", ""))
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


DB_NAME_RAG = os.getenv("POSTGRES_RAG_DB", "grossiste_rag")
DB_NAME_BUSINESS = os.getenv("POSTGRES_DB", "grossiste_mada")

DB_URL_RAG = _postgres_url("DB_RAG_URL", DB_NAME_RAG)
DB_URL_BUSINESS = _postgres_url("DB_BUSINESS_URL", DB_NAME_BUSINESS)


# Les fabriques ci-dessous sont paresseuses et mémoïsées : importer ce module ne
# doit ouvrir aucune connexion. Sans cela, ingest_docs.py ouvrait une session
# Neo4j dont il n'a aucun usage, et échouait si le graphe était arrêté.
@lru_cache(maxsize=None)
def get_llm():
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=MODEL_GEMINI,
        temperature=0,
        google_api_key=GOOGLE_API_KEY,
    )


@lru_cache(maxsize=None)
def get_embeddings():
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(
        model=MODEL_EMBEDDING,
        google_api_key=GOOGLE_API_KEY,
    )


@lru_cache(maxsize=None)
def get_graph():
    from langchain_neo4j import Neo4jGraph

    return Neo4jGraph(
        url=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        username=os.getenv("NEO4J_USERNAME", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", ""),
    )


@lru_cache(maxsize=None)
def get_engine(url: str):
    from sqlalchemy import create_engine

    return create_engine(url, pool_pre_ping=True)


def get_engine_rag():
    return get_engine(DB_URL_RAG)


def get_engine_business():
    return get_engine(DB_URL_BUSINESS)
