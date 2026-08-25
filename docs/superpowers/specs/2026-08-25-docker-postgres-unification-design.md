# Unification PostgreSQL Docker (un port, deux bases)

Date : 2026-08-25  
Statut : validé en conversation (architecture + composants)

## Contexte

Aujourd’hui Postgres est dupliqué :

- Docker `pgvector` exposé en **5433** : RAG (embeddings + FTS) et mémoire de conversation (LangGraph checkpointer).
- Postgres local / pgAdmin exposé en **5432** : données métier (`customers`, `sales`, `orders`, etc.), joignable depuis l’app via `host.docker.internal`.

Les deux instances s’appellent `grossiste_mada`. L’app doit jongler entre deux ports et deux hôtes.

Décision : **tout Postgres vit dans Docker**, **un seul port hôte**, **pas de pgAdmin**. Les données locales 5432 sont jetables (pas de `pg_dump`). Neo4j (Graph RAG) reste dans Docker, inchangé.

## Objectif

Un container Postgres unique (`pgvector/pgvector:pg16`) :

- Port hôte **5432** uniquement (`5432:5432`). Plus de 5433.
- Base **`grossiste_mada`** : métier.
- Base **`grossiste_rag`** : pgvector, FTS, conversations.
- Dans Compose, l’app utilise l’hôte interne `db` (plus de `host.docker.internal`). Depuis la machine hôte, `localhost:5432` pointe vers ce même container.

Hors scope : pgAdmin (local ou Docker), migration des données locales, changement Neo4j, seed métier.

## Architecture

```
Hôte
 ├── 8501  → app (Streamlit)
 ├── 5432  → db (pgvector/pg16)     ← unique port Postgres
 ├── 7474  → neo4j browser
 └── 7687  → neo4j bolt

Réseau Docker
  app ──► db:5432 / grossiste_mada     métier
  app ──► db:5432 / grossiste_rag      RAG + conversations
  app ──► neo4j:7687                   Graph RAG
```

## Composants

### Container `db`

- Image : `pgvector/pgvector:pg16` (inchangée).
- `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=admin`, `POSTGRES_DB=grossiste_mada`.
- Ports : `5432:5432`.
- Volume : `pgdata` (données persistantes).
- Init : `./initdb` monté sur `/docker-entrypoint-initdb.d` (exécuté seulement si `pgdata` est vide).
- Healthcheck : `pg_isready -U postgres -d grossiste_mada`.

### Scripts d’init (`initdb/`)

Un script shell unique `01-init.sh` (nécessaire pour cibler deux bases ; les `.sql` du point d’entrée officiel ne s’exécutent que sur `POSTGRES_DB`) :

1. `CREATE DATABASE grossiste_rag;`
2. Sur `grossiste_rag` : `CREATE EXTENSION IF NOT EXISTS vector;`
3. Sur `grossiste_mada` : schéma métier vide ci-dessous.

Les tables LangChain (`langchain_pg_collection`, `langchain_pg_embedding`) et LangGraph checkpoint sont créées par le code (`ingest.py`, `PostgresSaver.setup()`), pas par l’init.

### Schéma métier (`grossiste_mada`)

Tables vides, structure minimale pour `sql_database_tool` :

- `customers` : `id`, `name`, `email`, `city`, `created_at`
- `products` : `id`, `name`, `sku`, `category`, `unit_price`
- `employees` : `id`, `name`, `role`, `hired_at`
- `orders` : `id`, `customer_id` → `customers`, `employee_id` → `employees`, `order_date`, `status`
- `sales` : `id`, `order_id` → `orders`, `product_id` → `products`, `quantity`, `unit_price`, `line_total` (généré : `quantity * unit_price`)

Pas de lignes de seed.

### Container `app`

`depends_on` avec `condition: service_healthy` pour `db`.

Variables injectées par Compose (prioritaires sur `.env`) :

| Variable | Valeur |
|----------|--------|
| `DB_URL` | `postgresql+psycopg2://postgres:admin@db:5432/grossiste_rag` |
| `DB_RAG_URL` | identique à `DB_URL` |
| `DB_BUSINESS_URL` | `postgresql+psycopg2://postgres:admin@db:5432/grossiste_mada` |

### Code Python

Défauts dans le code (run hors Compose, via `localhost:5432`). Compose les surcharge avec l’hôte `db`.

- `agent_service.py` : `DB_RAG_URL` → `grossiste_rag` ; `DB_BUSINESS_URL` → `grossiste_mada`. Plus de `host.docker.internal`. Retirer les mentions de ports 5432/5433 dans les docstrings et le system prompt.
- `rag_service.py` et `ingest.py` : `DB_URL` par défaut vers `localhost:5432/grossiste_rag`.
- `ingest_graph.py` / Neo4j : aucun changement fonctionnel.

### Documentation

`README.md` et `.env.exemple` : un Postgres, port 5432, deux bases, plus de base métier locale. Mentionner que l’init ne tourne que sur volume neuf.

## Flux de données

1. `docker compose up` démarre `db` ; si volume vide, `01-init.sh` crée `grossiste_rag` + extension `vector` + tables métier.
2. L’app attend que Postgres soit ready, puis `PostgresSaver.setup()` crée les tables de checkpoint dans `grossiste_rag`.
3. `ingest.py` écrit embeddings + FTS dans `grossiste_rag`.
4. `sql_database_tool` n’exécute que des `SELECT` sur `engine_business` (`grossiste_mada`).
5. `rag_search_tool` et le checkpointer n’utilisent que `grossiste_rag`.
6. `graph_rag_tool` continue d’utiliser Neo4j.

## Gestion d’erreurs

- Volume `pgdata` déjà existant (ancien mapping 5433) : les scripts d’init **ne rejouent pas**. Il faut recréer le volume (`docker compose down -v`) — cela **efface** embeddings et conversations déjà stockés dans Docker. Consentement explicite requis avant cette commande.
- Port 5432 hôte encore pris par Postgres local : le container `db` ne démarre pas. Arrêter le service local avant.
- `sql_database_tool` : inchangé (`SELECT` only) ; isolation par base, pas seulement par prompt.

## Vérification

1. Arrêter Postgres local si présent ; `docker compose up -d --build`.
2. `docker compose exec db psql -U postgres -c '\l'` : `grossiste_mada` et `grossiste_rag` existent.
3. `docker compose exec db psql -U postgres -d grossiste_rag -c '\dx'` : extension `vector`.
4. `docker compose exec db psql -U postgres -d grossiste_mada -c '\dt'` : les cinq tables métier.
5. App Streamlit sur `http://localhost:8501` ; une question métier et une question documents n’utilisent plus deux ports Postgres.

## Hors scope

- pgAdmin (local ou container).
- Import des données du Postgres local 5432.
- Seed des tables métier.
- Modification du Graph RAG Neo4j.
- Exposition d’un second port Postgres.
