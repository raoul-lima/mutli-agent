import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector

load_dotenv()

DB_URL = os.getenv("DB_URL", "postgresql+psycopg2://postgres:admin@localhost:5432/grossiste_mada")
COLLECTION_NAME = "documents_entreprise"
DOCS_DIR = "./docs"

def setup_fts_in_postgres(engine):
    """Crée la colonne tsvector et l'index GIN dans PostgreSQL pour la recherche textuelle FTS."""
    print("4. Configuration de l'index Full-Text Search (tsvector) dans PostgreSQL...")
    with engine.connect() as conn:
        # Activer pgvector au cas où
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        
        # Ajouter la colonne text_tsv si elle n'existe pas
        conn.execute(text("""
            ALTER TABLE langchain_pg_embedding 
            ADD COLUMN IF NOT EXISTS text_tsv tsvector;
        """))
        
        # Mettre à jour la colonne text_tsv avec la représentation tsvector du document en français
        conn.execute(text("""
            UPDATE langchain_pg_embedding 
            SET text_tsv = to_tsvector('french', document)
            WHERE text_tsv IS NULL;
        """))
        
        # Créer l'index GIN pour accélérer les recherches de mots-clés exacts
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_langchain_pg_embedding_text_tsv 
            ON langchain_pg_embedding USING GIN (text_tsv);
        """))
        conn.commit()
    print("✓ Indexation Full-Text Search (GIN / tsvector) configurée avec succès !")

def ingest_docs():
    print(f"1. Chargement des PDF depuis '{DOCS_DIR}'...")
    loader = PyPDFDirectoryLoader(DOCS_DIR)
    documents = loader.load()

    if not documents:
        print("Aucun document PDF trouvé dans ./docs !")
        return

    print(f"-> {len(documents)} page(s) chargée(s).")

    print("2. Découpage du texte en chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(documents)

    print("3. Vectorisation et sauvegarde dans PGVector...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-2",
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )

    PGVector.from_documents(
        embedding=embeddings,
        documents=splits,
        collection_name=COLLECTION_NAME,
        connection=DB_URL,
        use_jsonb=True,
    )
    
    # Configuration FTS dans la base
    engine = create_engine(DB_URL)
    setup_fts_in_postgres(engine)
    
    print("✓ Ingestion hybride (PGVector + tsvector) terminée avec succès !")

if __name__ == "__main__":
    ingest_docs()