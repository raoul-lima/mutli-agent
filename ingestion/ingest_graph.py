"""Construction du knowledge graph Neo4j à partir des PDF.

Lancement : `python -m ingestion.ingest_graph` depuis la racine du projet.
"""

from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

from configs import PATH_DOCS, get_graph, get_llm


def build_knowledge_graph():
    print("1. Connexion à Neo4j...")
    graph = get_graph()

    print("2. Chargement des documents PDF...")
    loader = PyPDFDirectoryLoader(PATH_DOCS)
    docs = loader.load()

    if not docs:
        print(f"Aucun document PDF trouvé dans {PATH_DOCS} !")
        return

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    splits = text_splitter.split_documents(docs)

    print("3. Extraction des Entités et Relations avec Gemini...")
    # Transformation du texte brut en triplets (Entité -> RELATION -> Entité)
    llm_transformer = LLMGraphTransformer(llm=get_llm())
    graph_documents = llm_transformer.convert_to_graph_documents(splits)

    # Purge tardive : le graphe est entièrement dérivé des PDF, mais on attend que
    # l'extraction ait réussi pour ne pas se retrouver avec un graphe vide en cas d'échec.
    print("4. Réinitialisation du graphe existant...")
    graph.query("MATCH (n) DETACH DELETE n")

    print("5. Insertion dans le Knowledge Graph Neo4j...")
    graph.add_graph_documents(graph_documents)

    counts = graph.query(
        "MATCH (n) WITH count(n) AS noeuds "
        "MATCH ()-[r]->() RETURN noeuds, count(r) AS relations"
    )
    print(f"✓ Knowledge Graph reconstruit : {counts[0]['noeuds']} nœuds, {counts[0]['relations']} relations.")


if __name__ == "__main__":
    build_knowledge_graph()
