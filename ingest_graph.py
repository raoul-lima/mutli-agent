import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_neo4j import Neo4jGraph

load_dotenv()

def build_knowledge_graph():
    print("1. Connexion à Neo4j...")
    graph = Neo4jGraph(
        url=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
        username=os.getenv("NEO4J_USERNAME", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password123")
    )

    print("2. Chargement des documents PDF...")
    loader = PyPDFDirectoryLoader("./docs")
    docs = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    splits = text_splitter.split_documents(docs)

    print("3. Extraction des Entités et Relations avec Gemini...")
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Transformation du texte brut en triplets (Entité -> RELATION -> Entité)
    llm_transformer = LLMGraphTransformer(llm=llm)
    graph_documents = llm_transformer.convert_to_graph_documents(splits)

    print("4. Insertion dans le Knowledge Graph Neo4j...")
    graph.add_graph_documents(graph_documents)
    print("✓ Knowledge Graph construit avec succès dans Neo4j !")

if __name__ == "__main__":
    build_knowledge_graph()