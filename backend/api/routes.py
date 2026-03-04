from __future__ import annotations
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query as QueryParam

from api.schemas import (
    CacheControlRequest,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    RecommendationRequest,
    RecommendationResponse,
    SessionInfo,
    SessionSummary,
    SessionListResponse,
    ValidationInfo,
    VectorSearchRequest,
    VectorSearchResponse,
    PaginationInfo,
)
from core.query_router import QueryType, route_query
from db.neo4j_client import get_schema_fallback, health_check
from services.agent_service import run_agent_query
from services.cache_service import (
    clear_all as clear_cache,
    get_cached,
    get_stats as cache_stats,
    store_in_cache,
)
from services.graph_service import run_graph_query
from services.hybrid_service import run_hybrid_search
from services.memory_service import (
    clear_session,
    delete_session,
    get_conversation_history,
    get_or_create_memory,
    save_turn,
    list_sessions,
)
from db.history_db import get_session as get_session_db, list_all_sessions
from services.recommendation_service import (
    recommend_by_author_network,
    recommend_similar_papers,
    recommend_trending_in_topic,
)
from services.vector_service import (
    search_authors_by_similarity,
    search_papers_by_similarity,
)
from config.prompts import CLARIFICATION_PROMPT, OUT_OF_DOMAIN_PROMPT
from models.gemini_client import generate_text
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# MAIN QUERY ENDPOINT
@router.post("/query", response_model=QueryResponse, summary="Process a natural language query")
async def process_query(request: QueryRequest) -> QueryResponse:
    """
    Main entry point for all natural language questions.

    Pipeline:
      1. Load conversation history from memory
      2. Check cache for identical previous answer
      3. Route the question to the correct pipeline
      4. Execute the pipeline
      5. Save the turn to memory
      6. Cache the result
      7. Return the structured response
    """
    start_time = time.perf_counter()
    session_id = request.session_id

    logger.info(
        "Query received | session=%s | q='%s.........'",
        session_id, request.question[:35].replace("\n", " "),
    )

    # Step 1: Load conversation history
    history = get_conversation_history(session_id)

    # Step 2: Cache lookup (skip if force_type is set)
    if not request.force_type:
        cached = get_cached(request.question, "AUTO")
        if cached:
            return QueryResponse(
                answer=cached.answer,
                query_type=cached.query_type,
                session_id=session_id,
                confidence_score=cached.confidence_score,
                explanation=cached.explanation,
                cached=True,
                execution_time_ms=0.0,
            )

    # Step 3: Route
    if request.force_type:
        try:
            query_type = QueryType(request.force_type.upper())
            routing_reasoning = "Manually overridden by user"
            clarification = None
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown force_type: {request.force_type}")
    else:
        routing = route_query(request.question, history)
        query_type = routing.query_type
        routing_reasoning = routing.reasoning
        clarification = routing.clarification_needed

    logger.info("Routed to: %s", query_type.value)

    # Step 4: Handle AMBIGUOUS — return clarification without hitting DB
    if query_type == QueryType.AMBIGUOUS:
        clarification_text = clarification or _generate_clarification(request.question)
        save_turn(session_id, request.question, clarification_text)
        return QueryResponse(
            answer=clarification_text,
            query_type=QueryType.AMBIGUOUS.value,
            session_id=session_id,
            confidence_score=0.0,
            explanation="Question requires clarification before a query can be constructed.",
            execution_time_ms=(time.perf_counter() - start_time) * 1000,
        )

    # Step 4b: Handle OUT_OF_DOMAIN — return polite decline without hitting DB
    if query_type == QueryType.OUT_OF_DOMAIN:
        oof_text = _generate_out_of_domain(request.question)
        save_turn(session_id, request.question, oof_text)
        return QueryResponse(
            answer=oof_text,
            query_type=QueryType.OUT_OF_DOMAIN.value,
            session_id=session_id,
            confidence_score=0.0,
            explanation="The question is entirely outside the scope of academic research.",
            execution_time_ms=(time.perf_counter() - start_time) * 1000,
        )

    # Step 4c: Handle GREETING — return polite greeting without hitting DB
    if query_type == QueryType.GREETING:
        greeting_text = _generate_greeting()
        save_turn(session_id, request.question, greeting_text)
        return QueryResponse(
            answer=greeting_text,
            query_type=QueryType.GREETING.value,
            session_id=session_id,
            confidence_score=1.0,
            explanation="User greeted the assistant.",
            execution_time_ms=(time.perf_counter() - start_time) * 1000,
        )

    # Step 5: Execute the correct pipeline
    answer = ""
    reasoning = routing_reasoning
    confidence_score = 1.0
    explanation = ""
    validation_info = None
    agent_steps = []
    total_count = 0
    has_more = False

    if query_type == QueryType.GRAPH_TRAVERSAL:
        result = run_graph_query(
            request.question,
            history,
            page=request.page,
            page_size=request.page_size,
        )
        answer = result.answer
        confidence_score = result.confidence_score
        explanation = result.explanation
        total_count = result.total_count
        has_more = result.has_more
        validation_info = ValidationInfo(
            confidence_score=result.confidence_score,
            issues=result.issues,
            cypher_used=result.cypher_used,
            retries=result.retries,
        )

    elif query_type == QueryType.VECTOR_SIMILARITY:
        result = search_papers_by_similarity(request.question, history=history)
        answer = result.answer
        explanation = result.explanation
        confidence_score = 0.85  # Vector results are always "confident" — threshold takes care of quality
        total_count = result.total_found

    elif query_type == QueryType.HYBRID:
        result = run_hybrid_search(request.question, history)
        answer = result.answer
        explanation = result.explanation
        confidence_score = 0.82
        total_count = result.total_found

    elif query_type == QueryType.AGENT_COMPLEX:
        result = run_agent_query(request.question, history)
        answer = result.answer
        explanation = f"Multi-step reasoning completed in {result.iterations} steps."
        reasoning = f"Agentic loop synthesized answer across {result.iterations} iterations."
        agent_steps = result.steps
        confidence_score = 0.9 if not result.error else 0.3

    # Step 6: Save to memory
    save_turn(session_id, request.question, answer)

    # Step 7: Cache
    store_in_cache(
        question=request.question,
        answer=answer,
        query_type=query_type.value,
        confidence_score=confidence_score,
        explanation=explanation,
    )

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info("Query complete in %.0fms | type=%s", elapsed_ms, query_type.value)

    return QueryResponse(
        answer=answer,
        query_type=query_type.value,
        session_id=session_id,
        confidence_score=confidence_score,
        explanation=explanation,
        reasoning=reasoning,
        validation=validation_info,
        pagination=PaginationInfo(
            page=request.page,
            page_size=request.page_size,
            total_count=total_count,
            has_more=has_more,
        ) if total_count > 0 else None,
        cached=False,
        execution_time_ms=elapsed_ms,
        agent_steps=agent_steps,
    )


# ======================================================================
# VECTOR SEARCH ENDPOINT
# ======================================================================

@router.post("/search/vector", response_model=VectorSearchResponse, summary="Semantic vector search")
async def vector_search(request: VectorSearchRequest) -> VectorSearchResponse:
    """Direct semantic similarity search over papers or authors."""
    if request.target == "authors":
        result = search_authors_by_similarity(request.query, request.top_k, request.threshold)
    else:
        result = search_papers_by_similarity(
            request.query,
            top_k=request.top_k,
            threshold=request.threshold,
            expand=request.expand_query,
        )
    return VectorSearchResponse(
        answer=result.answer,
        results=result.results,
        scores=result.scores,
        expanded_query=result.expanded_query,
        total_found=result.total_found,
    )


# ======================================================================
# RECOMMENDATION ENDPOINT
# ======================================================================

@router.post("/recommend", response_model=RecommendationResponse, summary="Get paper recommendations")
async def recommend(request: RecommendationRequest) -> RecommendationResponse:
    """
    Get personalised paper recommendations using one of three strategies:
      - content_based:  Papers similar to a given paper title
      - collaborative:  Papers from the author's collaboration network
      - trending:       Most cited recent papers in a topic
    """
    if request.strategy == "collaborative":
        result = recommend_by_author_network(request.query, request.top_k)
    elif request.strategy == "trending":
        result = recommend_trending_in_topic(
            request.query,
            since_year=request.since_year,
            top_k=request.top_k,
        )
    else:
        result = recommend_similar_papers(request.query, request.top_k)

    return RecommendationResponse(
        answer=result.answer,
        papers=result.papers,
        strategy=result.strategy,
        total=result.total,
        explanation=result.explanation,
    )


# ======================================================================
# SESSION MANAGEMENT
# ======================================================================

@router.get("/session/{session_id}", response_model=SessionInfo, summary="Get session history")
async def get_session(session_id: str) -> SessionInfo:
    """Retrieve the conversation history for a session."""
    memory = get_or_create_memory(session_id)
    session_data = get_session_db(session_id)
    return SessionInfo(
        session_id=session_id,
        title=session_data.get("title", "New Chat") if session_data else "New Chat",
        turn_count=memory.turn_count,
        history=memory.get_messages_list(),
    )


@router.get("/sessions", response_model=SessionListResponse, summary="List all active sessions")
async def get_all_sessions() -> SessionListResponse:
    """Return all persistent sessions with their titles."""
    sessions = list_all_sessions()
    return SessionListResponse(sessions=sessions)


@router.delete("/session/{session_id}", summary="Delete a session")
async def delete_session_endpoint(session_id: str) -> dict[str, str]:
    """Delete a session entirely from the system."""
    delete_session(session_id)
    return {"message": f"Session {session_id} deleted", "session_id": session_id}


@router.post("/session/new", summary="Generate a new session ID")
async def create_new_session() -> dict[str, str]:
    """Generate a fresh UUID-based session ID for the frontend."""
    new_id = str(uuid.uuid4())
    get_or_create_memory(new_id)          # Pre-initialise
    return {"session_id": new_id}


# ======================================================================
# HEALTH, CACHE, SCHEMA, SUGGESTIONS
# ======================================================================

@router.get("/health", response_model=HealthResponse, summary="System health check")
async def health() -> HealthResponse:
    """Check Neo4j connection, cache status, and application health."""
    neo4j_status = health_check()
    cache_status  = cache_stats()
    overall = "healthy" if neo4j_status.get("status") == "connected" else "degraded"
    return HealthResponse(
        status=overall,
        neo4j=neo4j_status,
        cache=cache_status,
    )


@router.get("/cache/stats", summary="Cache performance statistics")
async def get_cache_stats() -> dict[str, Any]:
    """Return cache hit rate, size, and configuration."""
    return cache_stats()


@router.delete("/cache", summary="Clear the query result cache")
async def clear_cache_endpoint() -> dict[str, Any]:
    """Clear all cached query results."""
    count = clear_cache()
    return {"cleared": count, "message": f"Removed {count} cached entries"}


@router.get("/schema", summary="Get Neo4j graph schema")
async def get_schema() -> dict[str, str]:
    """Return the current Neo4j database schema."""
    return {"schema": get_schema_fallback()}


@router.get("/suggestions", summary="Get suggested queries for the UI")
async def get_suggestions() -> dict[str, list[dict[str, str]]]:
    """
    Return an empty list of suggestions as requested.
    """
    return {"suggestions": []}


# ======================================================================
# PRIVATE HELPERS
# ======================================================================

def _generate_clarification(question: str) -> str:
    """Generate a clarification request message for ambiguous questions."""
    prompt = CLARIFICATION_PROMPT.format(question=question)
    try:
        return generate_text(prompt, temperature=0.4, max_tokens=200)
    except Exception:
        return (
            "Your question is a bit broad. Could you be more specific? For example:\n"
            "• 'Who authored a specific paper?'\n"
            "• 'Find papers similar to a research area'\n"
            "• 'Compare two specific researchers'"
        )

def _generate_out_of_domain(question: str) -> str:
    """Generate a polite decline for completely off-topic questions."""
    prompt = OUT_OF_DOMAIN_PROMPT.format(question=question)
    try:
        return generate_text(prompt, temperature=0.2, max_tokens=150)
    except Exception:
        return (
            "I am an AI-powered Research Assistant specialized in navigating this Academic Knowledge Graph. "
            "I cannot answer questions outside of academic research, papers, authors, and topics."
        )

def _generate_greeting() -> str:
    """Generate a polite greeting message."""
    try:
        prompt = "You are a Senior Research AI Assistant. The user said hello. Reply with a very brief, professional greeting and ask how you can help with their research today. Keep it to one or two sentences."
        return generate_text(prompt, temperature=0.5, max_tokens=100)
    except Exception:
        return "Hello! I am your Research Assistant. How can I help you explore the academic knowledge graph today?"
