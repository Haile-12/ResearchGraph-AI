from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from config.prompts import QUERY_EXPANSION_PROMPT
from config.settings import settings
from core.response_formatter import format_recommendation_response, generate_query_explanation, format_response
from db.neo4j_client import run_query
from models.embeddings import generate_query_embedding
from models.gemini_client import generate_text
from utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class VectorSearchResult:
    """Result from the vector similarity pipeline."""
    answer: str
    reasoning: str = ""
    results: list[dict[str, Any]] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    expanded_query: str = ""
    explanation: str = ""
    total_found: int = 0

def expand_query(query: str) -> str:
    prompt = QUERY_EXPANSION_PROMPT.format(query=query)
    try:
        expanded = generate_text(prompt, temperature=0.4, max_tokens=300)
        logger.debug("Expanded query '%s.........' → '%s.........'", query[:10], expanded[:40])
        return expanded
    except Exception as e:
        logger.warning("Query expansion failed, using original: %s", e)
        return query

def search_papers_by_similarity(
    query: str,
    top_k: int | None = None,
    threshold: float | None = None,
    expand: bool = True,
    history: str = "",
) -> VectorSearchResult:
    top_k     = top_k     or settings.vector_top_k
    threshold = threshold or settings.vector_similarity_threshold

    # Step 1: Expand query for better embedding
    expanded_query = expand_query(query) if expand else query

    # Step 2: Generate embedding for the (expanded) query
    try:
        query_vector = generate_query_embedding(expanded_query)
    except Exception as e:
        logger.error("Embedding generation failed: %s", e)
        return VectorSearchResult(
            answer=" Failed to generate embeddings for your query. Please try again.",
            expanded_query=expanded_query,
        )

    # Step 3: Query Neo4j vector index
    results = _run_paper_vector_query(query_vector, top_k, threshold)

    if not results:
        return VectorSearchResult(
            answer=(
                "No papers found with sufficient semantic similarity to your query "
                f"(threshold: {threshold}). Try a broader description."
            ),
            expanded_query=expanded_query,
            explanation=f"Searched paper embeddings with cosine similarity ≥ {threshold}",
        )

    scores = [r.get("score", 0.0) for r in results]

    # Step 4: Format response (using direct graph humanizer for better list output)
    formatted = format_response(
        question=query,
        results=results,
        query_type="VECTOR_SIMILARITY",
        conversation_history=history,
        confidence_score=0.85,
    )
    answer = formatted["answer"]
    reasoning = formatted["reasoning"]

    explanation = generate_query_explanation(
        question=query,
        cypher=f"VECTOR SEARCH on paper_embeddings | threshold={threshold} | top_k={top_k}",
        query_type="VECTOR_SIMILARITY",
    )

    return VectorSearchResult(
        answer=answer,
        reasoning=reasoning,
        results=results,
        scores=scores,
        expanded_query=expanded_query,
        explanation=explanation,
        total_found=len(results),
    )


def search_authors_by_similarity(
    query: str,
    top_k: int | None = None,
    threshold: float | None = None,
) -> VectorSearchResult:
    top_k     = top_k     or settings.vector_top_k
    threshold = threshold or settings.vector_similarity_threshold

    expanded = expand_query(query)
    try:
        query_vector = generate_query_embedding(expanded)
    except Exception as e:
        logger.error("Author embedding query failed: %s", e)
        return VectorSearchResult(answer="Failed to generate query embedding.")

    cypher = """
        CALL db.index.vector.queryNodes('author_embeddings', $top_k, $query_vector)
        YIELD node AS author, score
        WHERE score >= $threshold
        MATCH (author)-[:AFFILIATED_WITH]->(inst:Institution)
        RETURN
            author.name    AS name,
            author.h_index AS h_index,
            author.email   AS email,
            inst.name      AS institution,
            inst.country   AS country,
            score
        ORDER BY score DESC
    """
    try:
        records = run_query(cypher, {
            "top_k": top_k,
            "query_vector": query_vector,
            "threshold": threshold,
        })
    except Exception as e:
        logger.error("Author vector search failed: %s", e)
        return VectorSearchResult(answer=f"Search error: {e}")

    scores = [r.get("score", 0.0) for r in records]
    answer = format_recommendation_response(query, records, scores)

    return VectorSearchResult(
        answer=answer,
        results=records,
        scores=scores,
        expanded_query=expanded,
        total_found=len(records),
    )

def _run_paper_vector_query(
    query_vector: list[float],
    top_k: int,
    threshold: float,
) -> list[dict]:
    cypher = """
        CALL db.index.vector.queryNodes('paper_embeddings', $top_k, $query_vector)
        YIELD node AS paper, score
        WHERE score >= $threshold

        // Enrich with authors and topics via graph traversal
        OPTIONAL MATCH (a:Author)-[:AUTHORED]->(paper)
        OPTIONAL MATCH (paper)-[:COVERS_TOPIC]->(t:Topic)
        OPTIONAL MATCH (paper)-[:PUBLISHED_IN]->(j:Journal)

        WITH
            paper.title          AS title,
            paper.year           AS year,
            paper.citations_count AS citations,
            paper.abstract       AS abstract,
            paper.doi            AS doi,
            collect(DISTINCT a.name) AS authors,
            collect(DISTINCT t.name) AS topics,
            j.name               AS journal,
            score

        RETURN title, year, citations, abstract, authors, topics, journal, score
        ORDER BY score DESC
    """
    try:
        return run_query(cypher, {
            "top_k": top_k,
            "query_vector": query_vector,
            "threshold": threshold,
        })
    except Exception as e:
        logger.error("Paper vector query failed: %s", e)
        return []
