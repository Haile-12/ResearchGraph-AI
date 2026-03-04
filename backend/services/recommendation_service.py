from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from config.settings import settings
from core.response_formatter import (
    format_recommendation_response,
    generate_query_explanation,
)
from db.neo4j_client import run_query
from models.embeddings import generate_query_embedding
from services.vector_service import expand_query, _run_paper_vector_query
from utils.logger import get_logger
logger = get_logger(__name__)

@dataclass
class RecommendationResult:
    """Result from any recommendation strategy."""
    answer: str
    papers: list[dict[str, Any]] = field(default_factory=list)
    authors: list[dict[str, Any]] = field(default_factory=list)
    strategy: str = ""
    explanation: str = ""
    total: int = 0

def recommend_similar_papers(
    reference_title: str,
    top_k: int = 5,
    seen_titles: list[str] | None = None,
) -> RecommendationResult:
    seen_titles = seen_titles or []

    # Step 1: Fetch the reference paper and its embedding
    ref_records = run_query(
        """
        MATCH (p:Paper)
        WHERE toLower(p.title) CONTAINS toLower($title)
        RETURN p.title AS title, p.embedding AS embedding, p.abstract AS abstract
        LIMIT 1
        """,
        {"title": reference_title},
    )

    if not ref_records or not ref_records[0].get("embedding"):
        # Fallback: search by title text embedding
        logger.info("No stored embedding for '%s', using text embedding", reference_title)
        return _recommend_by_query(reference_title, top_k, seen_titles)

    ref_embedding = ref_records[0]["embedding"]
    ref_actual_title = ref_records[0]["title"]

    # Step 2: Vector search using stored embedding
    cypher = """
        CALL db.index.vector.queryNodes('paper_embeddings', $top_k, $embedding)
        YIELD node AS paper, score
        WHERE score >= $threshold
          AND NOT paper.title IN $exclude_titles
          AND NOT toLower(paper.title) CONTAINS toLower($ref_title)

        OPTIONAL MATCH (a:Author)-[:AUTHORED]->(paper)
        OPTIONAL MATCH (paper)-[:COVERS_TOPIC]->(t:Topic)
        OPTIONAL MATCH (paper)-[:PUBLISHED_IN]->(j:Journal)

        WITH
            paper.title           AS title,
            paper.year            AS year,
            paper.citations_count AS citations,
            paper.abstract        AS abstract,
            collect(DISTINCT a.name) AS authors,
            collect(DISTINCT t.name) AS topics,
            j.name                AS journal,
            score,
            // Citation boost: slightly up-rank highly cited papers
            score + (toFloat(paper.citations_count) / 1000000.0) AS boosted_score

        RETURN title, year, citations, abstract, authors, topics, journal, score
        ORDER BY boosted_score DESC
        LIMIT $top_k
    """
    results = run_query(cypher, {
        "top_k": top_k + len(seen_titles) + 5,   
        "embedding": ref_embedding,
        "threshold": settings.vector_similarity_threshold,
        "exclude_titles": seen_titles,
        "ref_title": reference_title,
    })

    # Ensure diversity: at most 2 papers per topic cluster
    results = _diversify_results(results, top_k)

    scores = [r.get("score", 0.0) for r in results]
    answer = format_recommendation_response(
        query=f"Papers similar to '{ref_actual_title}'",
        items=results,
        scores=scores,
    )
    explanation = generate_query_explanation(
        question=f"Papers similar to {reference_title}",
        cypher=f"VECTOR SIMILARITY on paper_embeddings relative to '{ref_actual_title}'",
        query_type="CONTENT_BASED_RECOMMENDATION",
    )
    return RecommendationResult(
        answer=answer,
        papers=results,
        strategy="content_based",
        explanation=explanation,
        total=len(results),
    )

def recommend_by_author_network(
    author_name: str,
    top_k: int = 5,
) -> RecommendationResult:
    records = run_query(
        """
        MATCH (ref:Author)
        WHERE toLower(ref.name) CONTAINS toLower($author_name)
        WITH ref LIMIT 1

        // Find collaborators' papers that ref hasn't authored
        MATCH (ref)-[:COLLABORATED_WITH]-(collab:Author)
        MATCH (collab)-[:AUTHORED]->(paper:Paper)
        WHERE NOT (ref)-[:AUTHORED]->(paper)

        OPTIONAL MATCH (paper)-[:COVERS_TOPIC]->(t:Topic)
        OPTIONAL MATCH (paper)-[:PUBLISHED_IN]->(j:Journal)

        RETURN
            paper.title           AS title,
            paper.year            AS year,
            paper.citations_count AS citations,
            collect(DISTINCT collab.name) AS recommended_by,
            collect(DISTINCT t.name)      AS topics,
            j.name                        AS journal
        ORDER BY paper.citations_count DESC
        LIMIT $top_k
        """,
        {"author_name": author_name, "top_k": top_k},
    )

    if not records:
        return RecommendationResult(
            answer=f"No collaboration-based recommendations found for '{author_name}'."
        )

    answer = format_recommendation_response(
        query=f"Papers from {author_name}'s collaboration network",
        items=records,
        scores=[1.0] * len(records), 
    )
    return RecommendationResult(
        answer=answer,
        papers=records,
        strategy="collaborative_graph",
        total=len(records),
    )

# Strategy 3: Trending by Topic
def recommend_trending_in_topic(
    topic_name: str,
    since_year: int = 2019,
    top_k: int = 5,
) -> RecommendationResult:
    records = run_query(
        """
        MATCH (t:Topic)
        WHERE toLower(t.name) CONTAINS toLower($topic_name)
        WITH t LIMIT 1

        MATCH (paper:Paper)-[:COVERS_TOPIC]->(t)
        WHERE paper.year >= $since_year

        OPTIONAL MATCH (a:Author)-[:AUTHORED]->(paper)
        OPTIONAL MATCH (paper)-[:PUBLISHED_IN]->(j:Journal)

        RETURN
            paper.title            AS title,
            paper.year             AS year,
            paper.citations_count  AS citations,
            t.name                 AS topic,
            collect(DISTINCT a.name) AS authors,
            j.name                 AS journal
        ORDER BY paper.citations_count DESC
        LIMIT $top_k
        """,
        {"topic_name": topic_name, "since_year": since_year, "top_k": top_k},
    )

    if not records:
        return RecommendationResult(
            answer=f"No trending papers found for topic '{topic_name}' since {since_year}."
        )

    scores = [
        min(1.0, r.get("citations", 0) / 10000.0)
        for r in records
    ]
    answer = format_recommendation_response(
        query=f"Trending {topic_name} papers since {since_year}",
        items=records,
        scores=scores,
    )
    return RecommendationResult(
        answer=answer,
        papers=records,
        strategy="trending_by_topic",
        total=len(records),
    )

# Helper functions
def _recommend_by_query(
    query: str,
    top_k: int,
    seen_titles: list[str],
) -> RecommendationResult:
    """Fallback: use query expansion + embedding when reference paper has no stored vector."""
    expanded = expand_query(query)
    try:
        vector = generate_query_embedding(expanded)
    except Exception as e:
        return RecommendationResult(answer=f"Could not generate embeddings: {e}")

    results = _run_paper_vector_query(
        query_vector=vector,
        top_k=top_k + 5,
        threshold=settings.vector_similarity_threshold,
    )
    results = [r for r in results if r.get("title") not in seen_titles][:top_k]
    scores = [r.get("score", 0.0) for r in results]
    answer = format_recommendation_response(query, results, scores)
    return RecommendationResult(
        answer=answer, papers=results, strategy="query_embedding",
        total=len(results),
    )

def _diversify_results(results: list[dict], top_k: int) -> list[dict]:
    topic_counts: dict[str, int] = {}
    diverse = []
    overflow = []

    for paper in results:
        topics = paper.get("topics", [])
        primary_topic = topics[0] if topics else "Unknown"
        count = topic_counts.get(primary_topic, 0)

        if count < 2:
            diverse.append(paper)
            topic_counts[primary_topic] = count + 1
        else:
            overflow.append(paper)

        if len(diverse) >= top_k:
            break

    # Fill remaining slots from overflow if needed
    remaining = top_k - len(diverse)
    if remaining > 0:
        diverse.extend(overflow[:remaining])

    return diverse[:top_k]
