from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any
from config.prompts import CYPHER_GENERATION_PROMPT
from config.settings import settings
from core.response_formatter import format_response, generate_query_explanation
from db.neo4j_client import get_schema_fallback, run_query
from models.embeddings import generate_query_embedding
from models.gemini_client import generate_text
from services.vector_service import expand_query
from utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class HybridSearchResult:
    """Result from the hybrid search pipeline."""
    answer: str
    reasoning: str = ""
    results: list[dict[str, Any]] = field(default_factory=list)
    semantic_query: str = ""
    graph_filter: str = ""
    explanation: str = ""
    total_found: int = 0
    scores: list[float] = field(default_factory=list)

def run_hybrid_search(
    question: str,
    conversation_history: str = "",
) -> HybridSearchResult:
    """
    Execute the hybrid pipeline.
    """
    # Step 1: Decompose the question into semantic + graph parts
    semantic_part, graph_filter_cypher = _decompose_hybrid_question(
        question, conversation_history
    )
    logger.info(
        "Hybrid decomposition — semantic: '%s', filter: '%s'",
        semantic_part[:80],
        graph_filter_cypher[:80],
    )

    # Step 2: Generate embedding for the semantic part
    expanded = expand_query(semantic_part)
    try:
        query_vector = generate_query_embedding(expanded)
    except Exception as e:
        logger.error("Embedding failed in hybrid search: %s", e)
        return HybridSearchResult(
            answer="Failed to generate query embedding.",
            semantic_query=semantic_part,
        )

    # Step 3: Run hybrid Cypher combining vector + graph
    results = _run_hybrid_cypher(
        query_vector=query_vector,
        filter_conditions=graph_filter_cypher,
        top_k=settings.vector_top_k * 2,
        threshold=settings.vector_similarity_threshold,
    )

    if not results:
        return HybridSearchResult(
            answer=(
                "No papers matched both the semantic similarity AND the graph constraints. "
                "Try relaxing one of the conditions."
            ),
            reasoning=f"Decomposition suggested semantic search for '{semantic_part}' and graph filter '{graph_filter_cypher}', but the intersection was empty.",
            semantic_query=semantic_part,
            graph_filter=graph_filter_cypher,
        )

    scores = [r.get("score", 0.0) for r in results]

    formatted = format_response(
        question=question,
        results=results,
        query_type="HYBRID",
        conversation_history=conversation_history,
    )
    answer = formatted["answer"]
    reasoning = formatted["reasoning"]

    explanation = generate_query_explanation(
        question=question,
        cypher=f"HYBRID: vector({semantic_part[:50]}) + graph({graph_filter_cypher[:80]})",
        query_type="HYBRID",
    )

    return HybridSearchResult(
        answer=answer,
        reasoning=reasoning,
        results=results,
        semantic_query=semantic_part,
        graph_filter=graph_filter_cypher,
        explanation=explanation,
        total_found=len(results),
        scores=scores,
    )

# Question Decomposition
def _decompose_hybrid_question(
    question: str,
    conversation_history: str,
) -> tuple[str, str]:
    schema = get_schema_fallback()
    decomposition_prompt = f"""
You are analyzing a hybrid question that has BOTH a semantic component (meaning/theme)
and a structural component (graph relationships).

Schema:
{schema}

Question: {question}
Conversation history: {conversation_history or "None"}

Split this question into:
1. SEMANTIC_PART: The thematic/meaning component to search for by embedding similarity.
   This should be descriptive text, NOT a Cypher query.

2. GRAPH_FILTER: A valid Cypher WHERE clause (or MATCH conditions) to filter results
   by structural graph constraints. This comes AFTER the vector search finds candidates.
   Variable 'paper' refers to the matched Paper node.
   Variables available: paper, author (Author who wrote it), inst (author's Institution),
   topic (Topic covered by paper), journal (Journal published in).

Example input: "Reinforcement learning papers by authors at DeepMind with over 1000 citations"
Example output:
SEMANTIC_PART: Reinforcement learning, reward-based learning, policy gradient, Q-learning
GRAPH_FILTER: AND inst.name = 'DeepMind' AND paper.citations_count > 1000

Respond with EXACTLY this format (two lines):
SEMANTIC_PART: <the semantic description>
GRAPH_FILTER: <the cypher filter conditions, or empty string if no structural filter>
"""

    try:
        raw = generate_text(decomposition_prompt, temperature=0.1)
        lines = {
            line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip()
            for line in raw.strip().split("\n")
            if ":" in line
        }
        semantic = lines.get("SEMANTIC_PART", question)
        graph_filter = lines.get("GRAPH_FILTER", "")
    except Exception as e:
        logger.warning("Decomposition failed, using full question as semantic: %s", e)
        semantic = question
        graph_filter = ""

    return semantic, graph_filter

# Hybrid Cypher Execution
def _run_hybrid_cypher(
    query_vector: list[float],
    filter_conditions: str,
    top_k: int,
    threshold: float,
) -> list[dict]:
    """
    Execute the hybrid Cypher query:
      - Vector search on paper_embeddings to get semantic candidates
      - Graph traversal to join with authors, institutions, topics
      - Apply the structural filter conditions
    """
    # Sanitise the filter_conditions — strip leading AND/WHERE for safe injection
    filter_str = filter_conditions.strip()
    filter_str = re.sub(r"^(AND|WHERE)\s+", "", filter_str, flags=re.IGNORECASE)

    # Build dynamic WHERE condition
    where_clause = f"AND {filter_str}" if filter_str else ""

    cypher = f"""
        CALL db.index.vector.queryNodes('paper_embeddings', $top_k, $query_vector)
        YIELD node AS paper, score
        WHERE score >= $threshold

        // Join with graph for structural filtering
        OPTIONAL MATCH (author:Author)-[:AUTHORED]->(paper)
        OPTIONAL MATCH (author)-[:AFFILIATED_WITH]->(inst:Institution)
        OPTIONAL MATCH (paper)-[:COVERS_TOPIC]->(topic:Topic)
        OPTIONAL MATCH (paper)-[:PUBLISHED_IN]->(journal:Journal)

        // Apply structural filter from decomposition
        WITH paper, author, inst, topic, journal, score
        WHERE paper IS NOT NULL {where_clause}

        RETURN
            paper.title             AS title,
            paper.year              AS year,
            paper.citations_count   AS citations,
            paper.abstract          AS abstract,
            collect(DISTINCT author.name) AS authors,
            collect(DISTINCT inst.name)   AS institutions,
            collect(DISTINCT topic.name)  AS topics,
            journal.name            AS journal,
            score
        ORDER BY score DESC
        LIMIT 10
    """
    try:
        results = run_query(cypher, {
            "top_k": top_k,
            "query_vector": query_vector,
            "threshold": threshold,
        })
        logger.info("Hybrid query returned %d results", len(results))
        return results
    except Exception as e:
        logger.error("Hybrid cypher failed: %s\nCypher: %s", e, cypher[:300])
        return []
