Priorité haute (valeur rapide)
Upload PDF depuis Streamlit
Aujourd’hui il faut mettre les fichiers dans ./docs + relancer ingest.py. Un bouton “Importer” + ré-ingestion ciblée rendrait le produit utilisable sans Docker CLI.

Schéma SQL exposé à l’agent
sql_database_tool accepte du SQL brut sans connaître tables/colonnes. Ajouter un outil describe_schema (ou injecter le schéma dans le prompt) réduit beaucoup les erreurs SQL.

Corriger le prompt système
Il dit “3 outils” et omet graph_rag_tool. Aligner prompt ↔ outils + règles de routing claires (quand utiliser RAG vs SQL vs graphe).

Réponses sourcées dans l’UI
Afficher citations (fichier + page) et éventuellement un extrait cliquable, pas seulement la liste des outils.

Ré-ingestion idempotente
Éviter les doublons si on relance ingest.py (supprimer la collection / dédoublonner par source + hash).

Priorité moyenne (qualité agent)
Routeur multi-agents
Au lieu d’un seul ReAct fourre-tout : un supervisor qui route vers Agent Docs / Agent SQL / Agent Graphe. Plus stable sur les questions mixtes.

Streaming des tokens
Remplacer le spinner bloquant par un stream Streamlit (st.write_stream) pour un ressenti plus “chat GPT”.

Mémoire longue
Résumer les vieux tours quand le thread grossit (sinon coût + bruit contextuel).

Reranking
Après le RRF hybride, un petit modèle de rerank (ou LLM) sur le top-20 → top-3 améliore souvent la pertinence.

Évaluation RAG
Jeu de Q/R + métriques (hit rate, faithfulness) via Langfuse ou un script eval.py — indispensable pour itérer sans “au feeling”.

Priorité “produit / prod”
Auth simple sur Streamlit (mot de passe ou SSO) — l’app expose SQL + Python REPL.
Sécuriser le Python REPL (sandbox, timeout, whitelist) ou le retirer en prod.
Cache embeddings / réponses pour les questions fréquentes.
Healthcheck + logs (DB, Neo4j, Gemini) dans l’UI ou /health.
CI minimale : lint + un test d’ingestion mockée + test de hybrid_search avec fixtures.
Idées différenciantes (Grossiste Mada)
Tableau de bord “insights” : top produits, retards, alertes — généré périodiquement via SQL + graphe.
Alertes proactives : “contrat X expire dans 30 jours” (cron + Neo4j/RAG).
Mode “expliquer ma requête” : montrer le Cypher / SQL généré pour audit métier.
Multilingue FR/MG si pertinent côté utilisateurs.
Suggestion de roadmap courte (2–3 sprints)

upload + anti-doublons + prompt/routing
schéma SQL + citations UI + streaming
eval + rerank (ou multi-agent si les questions mixtes deviennent le vrai pain)
Si tu veux, on peut en implémenter une tout de suite — la plus rentable serait souvent upload PDF + schéma SQL + fix du prompt.