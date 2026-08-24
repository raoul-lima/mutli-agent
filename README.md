# Agent IA Grossiste Mada

Assistant multi-outils pour Grossiste Mada : documents PDF (RAG hybride), base métier SQL, graphe de connaissances Neo4j, et calculs Python — avec mémoire de conversation persistante.

## Architecture

```
Utilisateur (Streamlit)
        │
        ▼
   LangGraph Agent (ReAct)  ←── mémoire PostgreSQL (checkpointer)
        │
        ├── rag_search_tool         → PGVector + Full-Text Search (RRF)
        ├── describe_schema_tool    → schéma tables/colonnes (base métier)
        ├── sql_database_tool       → PostgreSQL métier (SELECT only)
        ├── graph_rag_tool          → Neo4j (relations / hiérarchies)
        └── python_calculator_tool  → Python REPL
```

| Composant | Rôle |
|-----------|------|
| **Streamlit** (`app.py`) | Interface chat + sessions (`thread_id`) |
| **LangGraph** (`agent_service.py`) | Agent ReAct + outils + mémoire |
| **PostgreSQL + pgvector** | Embeddings RAG + FTS + checkpointer |
| **Neo4j** | Knowledge graph (entités / relations) |
| **Gemini** | LLM + embeddings |
| **Langfuse** | Observabilité des traces |

## Prérequis

- Docker & Docker Compose
- Clé API Google (`GOOGLE_API_KEY`)
- Compte Langfuse (optionnel, pour le monitoring)
- PDFs à indexer dans `./docs`

## Démarrage rapide

### 1. Configuration

```bash
cp .env.exemple .env
```

Renseigner au minimum :

```env
GOOGLE_API_KEY=votre_clé

LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com

NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password123
```

### 2. Lancer les services

```bash
docker compose up -d --build
```

Services exposés :

| Service | URL / Port |
|---------|------------|
| App Streamlit | http://localhost:8501 |
| PostgreSQL (RAG) | localhost:5433 |
| Neo4j Browser | http://localhost:7474 |
| Neo4j Bolt | localhost:7687 |

### 3. Ingérer les documents

Placer les PDF dans `./docs`, puis :

```bash
# RAG hybride (vecteurs + full-text search)
docker compose exec app python ingest.py

# Knowledge graph Neo4j
docker compose exec app python ingest_graph.py
```

### 4. Utiliser l’agent

Ouvrir http://localhost:8501 et poser des questions.  
Chaque conversation a un `thread_id` ; le bouton **Nouvelle Conversation** réinitialise le contexte.

## Ingestion RAG (`ingest.py`)

1. Chargement des PDF depuis `./docs`
2. Découpage en chunks (1000 / overlap 200)
3. Vectorisation Gemini → PGVector
4. Index Full-Text Search (`tsvector` + GIN)

La recherche combine similarité vectorielle et mots-clés via **RRF** (Reciprocal Rank Fusion).

## Ingestion graphe (`ingest_graph.py`)

1. Connexion Neo4j  
2. Chargement / découpage des PDF  
3. Extraction d’entités et relations (LLM)  
4. Insertion dans le knowledge graph  

## Structure du projet

```
mutli-agent/
├── app.py              # UI Streamlit
├── agent_service.py    # Agent LangGraph + outils
├── rag_service.py      # Recherche hybride PostgreSQL
├── ingest.py           # Ingestion PDF → PGVector + FTS
├── ingest_graph.py     # Ingestion PDF → Neo4j
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.exemple
└── docs/               # PDFs à indexer (gitignored)
```

## Exemples de questions

- *Quelles sont les règles RH sur les congés ?* → `rag_search_tool`
- *Quelles tables / colonnes existe-t-il ?* → `describe_schema_tool`
- *Combien de commandes a passé le client X ?* → `describe_schema_tool` puis `sql_database_tool`
- *Quelles entités sont liées à ce contrat ?* → `graph_rag_tool`
- *Calcule le total et la moyenne de ces montants* → `python_calculator_tool`

## Notes

- `sql_database_tool` n’autorise que les requêtes `SELECT`.
- Avant une requête SQL, l’agent doit appeler `describe_schema_tool` pour connaître le schéma exact.
- La base métier (`DB_BUSINESS_URL`) est distincte de la base RAG (`DB_RAG_URL` / `DB_URL`).
- Les secrets (`.env`) et le contenu de `docs/` ne sont pas versionnés.
