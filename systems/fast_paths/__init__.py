"""Chemins rapides : outil direct + un LLM, sans sous-agent ReAct."""

from systems.fast_paths.docs import answer_docs_question
from systems.fast_paths.graph import answer_graph_question
from systems.fast_paths.mixed import answer_mixed_question
from systems.fast_paths.sql import answer_sql_question

__all__ = ["answer_docs_question", "answer_graph_question", "answer_sql_question"]
