# Agent IA Grossiste Mada

Assistant multi-outils pour Grossiste Mada : documents PDF (RAG hybride), base métier SQL, graphe de connaissances Neo4j, et calculs Python — avec mémoire de conversation persistante.

## Architecture

Un **routeur léger** classe chaque question en un seul appel structuré (ou via
heuristiques instantanées). Les questions simples passent en **fast path** (~2 appels
LLM) ; les questions mixtes ou conversationnelles montent au **superviseur** avec ses
sous-agents spécialisés.

```
Utilisateur (Streamlit)
        │
        ▼
   Routeur (structuré)     ← heuristiques ou 1 appel LLM
        │
        ├── docs  → fast_docs  → rag_search hybride + 1 LLM
        ├── sql   → fast_sql   → text-to-SQL + sql_database + 1 LLM
        ├── sql   → fast_sql   → text-to-SQL + sql_database + 1 LLM
        ├── graph → fast_graph → graph_rag direct
        ├── mixed → fast_mixed → fast_docs ∥ fast_sql + synthèse (docs+sql)
        │
        └── mixed+graph / chat / échec fast path
                │
                ▼
           Superviseur (ReAct)  ←── mémoire PostgreSQL (checkpointer)
                │
                ├── ask_docs_agent(question)   → Agent Docs   → rag_search
                ├── ask_sql_agent(question)    → Agent SQL    → sql_database
                ├── ask_graph_agent(question)  → Agent Graphe → graph_rag
                └── python_calculator_tool
```

| Type de question | Chemin | Outils affichés |
|------------------|--------|-----------------|
| Règles RH, CGV, procédures | `fast_docs` | ~2 appels LLM |
| Comptages, listes métier | `fast_sql` | ~2 appels LLM |
| Relations entre entités | `fast_graph` | graph_rag |
| Règle + chiffre (docs + SQL) | `fast_mixed` | ~4–6 appels LLM |
| Règle + chiffre + graphe | Superviseur | `ask_*_agent` |

Chaque sous-agent du superviseur est lui-même une boucle ReAct : il peut corriger sa
requête après une erreur SQL ou reformuler sa recherche si les extraits sont hors sujet.

Sur une question mixte docs+SQL, le **fast path mixte** découpe, exécute `fast_docs` et
`fast_sql` en parallèle puis synthétise (~4–6 appels LLM). Le superviseur ne prend le
relais que pour le graphe, le suivi conversationnel ou si le fast path échoue.

| Composant | Rôle |
|-----------|------|
| **Streamlit** (`app.py`) | Interface chat + sessions (`thread_id`) |
| **Routeur** (`systems/router.py`) | Classification docs / sql / graph / mixed / chat |
| **Fast paths** (`systems/fast_paths/`) | RAG, SQL ou graphe direct sans sous-agent |
| **Superviseur** (`systems/supervisor.py`) | Questions mixtes, suivi conversationnel, fallback |
| **Sous-agents** (`systems/agents/`) | Un expert par source de vérité |
| **PostgreSQL + pgvector** | Embeddings RAG + FTS + checkpointer |
| **Neo4j** | Knowledge graph (entités / relations) |
| **Gemini** | LLM + embeddings |
| **LangSmith** | Observabilité des traces (optionnel) |

Le prix de la qualité sur les cas complexes (graphe, suivi chat) reste la latence du
superviseur ; la majorité des questions repassent en fast path (~5–20 s selon Gemini).

## Structure du projet

```
mutli-agent/
├── app.py                       # UI Streamlit (point d'entrée)
├── configs.py                   # Config partagée : URLs, chemins, clients LLM
├── systems/
│   ├── supervisor.py            #   superviseur, son prompt, le checkpointer
│   ├── runner.py                #   exécution d'une question (appelé par app.py)
│   ├── monitoring.py            #   statut du tracing LangSmith (barre latérale)
│   ├── agents/                  #   un module par spécialiste
│   │   ├── base.py              #     fabrique : agent ReAct emballé en outil
│   │   ├── docs.py              #     agent + prompt
│   │   ├── sql.py               #     agent + prompt + introspection du schéma
│   │   └── graph.py             #     agent + prompt
│   ├── tools/                   #   un module par outil (rag, sql, graph, python)
│   ├── services.py              #   recherche hybride pgvector + FTS
│   └── messages.py              #   helpers sur les messages LangChain
├── ingestion/                   # Scripts hors ligne
│   ├── ingest_docs.py           #   PDF → PGVector + FTS
│   ├── ingest_graph.py          #   PDF → Neo4j
│   └── migrate_csv.py           #   CSV → tables métier
├── initdb/01-init.sh            # Init Postgres : 2 bases + schéma métier
├── pgadmin/servers.json         # Serveurs pré-enregistrés dans pgAdmin
├── docs/
│   ├── files_entreprise/        #   PDF à indexer (non versionné)
│   └── csv_files/               #   CSV métier (non versionné)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

Les modules de `systems/` et `ingestion/` sont des packages : ils s'importent
depuis la racine (`from systems.tools import ...`) et les scripts se lancent
avec `python -m`, jamais par chemin de fichier.

Le prompt de chaque agent vit dans son propre module, à côté de la liste de ses outils :
on lit `systems/agents/sql.py` et on sait d'un coup ce que fait l'agent, avec quoi et
selon quelles instructions. **Ajouter un spécialiste** consiste à créer un module dans
`agents/`, y appeler `subagent_tool(...)`, et l'ajouter à la liste des outils du
superviseur — sans toucher aux agents existants.

## Prérequis

- Docker & Docker Compose
- Clé API Google (`GOOGLE_API_KEY`)
- Compte LangSmith (optionnel, pour le monitoring)
- PDF à indexer dans `docs/files_entreprise/`, CSV métier dans `docs/csv_files/`

## Démarrage rapide

### 1. Configuration

```bash
cp .env.example .env
```

Renseigner au minimum :

```env
GOOGLE_API_KEY=votre_clé

NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=votre_mot_de_passe

POSTGRES_USER=postgres
POSTGRES_PASSWORD=votre_mot_de_passe
POSTGRES_DB=grossiste_mada
POSTGRES_RAG_DB=grossiste_rag

PGADMIN_PASSWORD=votre_mot_de_passe
```

`docker-compose.yml` refuse de démarrer si `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`NEO4J_USERNAME` ou `NEO4J_PASSWORD` sont absents. Les identifiants ne vivent que
dans `.env` : Compose les injecte par interpolation et assemble lui-même
`DB_RAG_URL` / `DB_BUSINESS_URL` avec le hostname interne `db`. Hors conteneur,
`configs.py` reconstruit ces URLs vers `POSTGRES_HOST` (`localhost` par défaut).

Pour activer le monitoring, ajouter une clé LangSmith et passer le drapeau à `true` :

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=grossiste-mada
```

### 2. Lancer les services

```bash
docker compose up -d --build
```

| Service | URL / Port |
|---------|------------|
| App Streamlit | http://localhost:8501 |
| pgAdmin | http://localhost:5050 |
| PostgreSQL | localhost:5432 (`grossiste_mada` métier, `grossiste_rag` vecteurs + conversations) |
| Neo4j Browser | http://localhost:7474 |
| Neo4j Bolt | localhost:7687 |

pgAdmin s'ouvre sans écran de connexion et les deux bases sont déjà enregistrées
(`pgadmin/servers.json`). Au premier clic sur un serveur, saisir le mot de passe
`POSTGRES_PASSWORD` et cocher « Save password ».

### 3. Charger les données

```bash
# Données métier : CSV → tables customers / products / employees / orders / sales
docker compose exec app python -m ingestion.migrate_csv

# RAG hybride (vecteurs + full-text search)
docker compose exec app python -m ingestion.ingest_docs

# Knowledge graph Neo4j
docker compose exec app python -m ingestion.ingest_graph
```

### 4. Utiliser l'agent

Ouvrir http://localhost:8501 et poser des questions.
Chaque conversation a un `thread_id` ; le bouton **Nouvelle Conversation** réinitialise le contexte.

## Détail des scripts d'ingestion

### `ingestion/ingest_docs.py`

1. Chargement des PDF depuis `docs/files_entreprise/`
2. Découpage en chunks (1000 / overlap 200)
3. Vectorisation Gemini → PGVector (`pre_delete_collection`, donc idempotent)
4. Index Full-Text Search (`tsvector` + GIN)

La recherche combine similarité vectorielle et mots-clés via **RRF** (Reciprocal Rank Fusion).

### `ingestion/ingest_graph.py`

1. Chargement / découpage des PDF
2. Extraction d'entités et relations par le LLM
3. Purge puis réinsertion du graphe (la purge n'a lieu qu'après une extraction réussie)

### `ingestion/migrate_csv.py`

Charge les CSV dans une transaction unique, après contrôle des colonnes et de
l'intégrité référentielle : en cas d'échec, la base reste intacte. `--append`
conserve les lignes existantes au lieu de vider les tables.

## Observabilité (LangSmith)

Le tracing n'apparaît nulle part dans le code de l'agent : `langchain` et `langgraph`
instrumentent chaque appel dès que les variables d'environnement sont présentes. Il n'y a
donc aucun callback à câbler, mais aussi rien qui signale un tracing mal configuré — la
barre latérale de Streamlit affiche l'état résolu par `systems/monitoring.py`.

Trois pièges à connaître :

- `LANGSMITH_TRACING` doit valoir exactement `true`. `True`, `1` ou `yes` désactivent le
  tracing silencieusement.
- Sans `LANGSMITH_API_KEY`, le drapeau seul ne suffit pas. La barre latérale distingue
  ces deux cas.
- Les variables sont lues au démarrage du processus. Une variable ajoutée après le
  lancement de Streamlit n'est prise en compte qu'après redémarrage. Dans Docker,
  `docker-compose.yml` réinjecte explicitement les `LANGSMITH_*` dans le conteneur `app`.

Chaque tour de conversation est un run nommé `supervisor`, tagué `grossiste-mada`, avec
le `thread_id` en métadonnée : on peut filtrer une session entière dans LangSmith. Sous
ce run, un enfant par spécialiste (`ask_docs_agent`, `ask_sql_agent`, `ask_graph_agent`),
puis les appels d'outils de chacun. C'est la façon la plus directe de voir quelle
sous-question le superviseur a réellement transmise, et combien de tours d'auto-correction
un spécialiste a consommés.

## Exemples de questions

- *Quelles sont les règles RH sur les congés ?* → `ask_docs_agent`
- *Combien de clients avons-nous, et combien sont demi-grossistes ?* → `ask_sql_agent`
- *Quelles entités sont liées à ce contrat ?* → `ask_graph_agent`
- *Nos demi-grossistes respectent-ils les délais de paiement des CGV ?* → `ask_docs_agent` et `ask_sql_agent` en parallèle

L'interface affiche les spécialistes sollicités sous chaque réponse : c'est la façon la
plus simple de vérifier que le superviseur a routé correctement.

## Notes

- `sql_database` n'autorise que les requêtes `SELECT`, uniquement sur `grossiste_mada`.
- L'agent SQL lit le schéma métier depuis `information_schema` au premier appel plutôt que
  de le figer dans son prompt : ajouter une colonne ne demande aucune modification de code.
- Les sous-agents sont bornés par un `recursion_limit` : une boucle d'auto-correction qui
  n'aboutit pas rend la main au superviseur au lieu de tourner indéfiniment.
- Le modèle `gemini-3.5-flash-lite` ignore le paramètre `temperature` et émet un
  avertissement à chaque appel. C'est sans conséquence.
- RAG, FTS et la mémoire LangGraph vivent dans `grossiste_rag` (`DB_RAG_URL`).
- Tout le projet utilise le driver **psycopg3** (`postgresql+psycopg://`) : c'est le
  seul accepté par `PGVector`. `configs.py` normalise les URLs reçues.
- `initdb/01-init.sh` ne s'exécute que si le volume Docker `pgdata` est vide. Pour
  réinitialiser : `docker compose down -v` (efface embeddings et conversations).
- Le schéma métier de `initdb/01-init.sh` reprend exactement les en-têtes des CSV
  (en minuscules) ; `migrate_csv.py` refuse d'insérer en cas d'écart.
- `sales.id_commande` n'a pas de clé étrangère : `sales.csv` référence des commandes
  de 2025 absentes de `orders.csv`, qui ne couvre que 2026.
- Arrêter tout Postgres local sur le port 5432 avant `docker compose up`.
- Les secrets (`.env`), les PDF et les CSV ne sont pas versionnés.
