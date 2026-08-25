"""Ingestion des PDF vers PGVector + index full-text search.

Lancement : `python -m ingestion.ingest_docs` depuis la racine du projet.
"""

from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_postgres import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import text

from configs import (
    COLLECTION_NAME,
    DB_URL_RAG,
    PATH_DOCS,
    get_embeddings,
    get_engine_rag,
)


def setup_fts_in_postgres(engine):
    """Crée la colonne tsvector et l'index GIN dans PostgreSQL pour la recherche textuelle FTS."""
    print("4. Configuration de l'index Full-Text Search (tsvector) dans PostgreSQL...")
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

        conn.execute(text("""
            ALTER TABLE langchain_pg_embedding
            ADD COLUMN IF NOT EXISTS text_tsv tsvector;
        """))

        conn.execute(text("""
            UPDATE langchain_pg_embedding
            SET text_tsv = to_tsvector('french', document)
            WHERE text_tsv IS NULL;
        """))

        # Index GIN pour accélérer les recherches de mots-clés exacts.
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_langchain_pg_embedding_text_tsv
            ON langchain_pg_embedding USING GIN (text_tsv);
        """))
    print("✓ Indexation Full-Text Search (GIN / tsvector) configurée avec succès !")


def ingest_docs():
    print(f"1. Chargement des PDF depuis '{PATH_DOCS}'...")
    loader = PyPDFDirectoryLoader(PATH_DOCS)
    documents = loader.load()

    if not documents:
        print(f"Aucun document PDF trouvé dans {PATH_DOCS} !")
        return

    print(f"-> {len(documents)} page(s) chargée(s) depuis {len({d.metadata.get('source') for d in documents})} fichier(s).")

    print("2. Découpage du texte en chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(documents)

    print("3. Vectorisation et sauvegarde dans PGVector...")
    # pre_delete_collection : sans ça, chaque exécution ajoute une copie des chunks
    # existants (les ids sont générés aléatoirement), ce qui fausse la recherche.
    PGVector.from_documents(
        embedding=get_embeddings(),
        documents=splits,
        collection_name=COLLECTION_NAME,
        connection=DB_URL_RAG,
        use_jsonb=True,
        pre_delete_collection=True,
    )

    setup_fts_in_postgres(get_engine_rag())

    print("✓ Ingestion hybride (PGVector + tsvector) terminée avec succès !")


if __name__ == "__main__":
    ingest_docs()
