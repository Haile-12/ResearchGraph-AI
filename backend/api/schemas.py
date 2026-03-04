from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

# REQUEST MODELS
class QueryRequest(BaseModel):
    """Main chat query request — sent from the chat interface."""
    question: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Natural language question about the research knowledge graph",
        examples=["Who authored Attention Is All You Need?"],
    )
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique session identifier for conversation memory",
    )
    page: int = Field(default=1, ge=1, description="Page number for paginated results")
    page_size: int = Field(default=10, ge=1, le=50, description="Results per page")
    force_type: Optional[str] = Field(
        default=None,
        description="Override router: GRAPH_TRAVERSAL | VECTOR_SIMILARITY | HYBRID | AGENT_COMPLEX | OUT_OF_DOMAIN",
    )

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Question cannot be blank")
        return v.strip()


class RecommendationRequest(BaseModel):
    """Request for paper recommendations."""
    query: str = Field(
        ...,
        min_length=3,
        description="Paper title, topic, or description to recommend similar papers for",
    )
    strategy: str = Field(
        default="content_based",
        description="content_based | collaborative | trending",
    )
    top_k: int = Field(default=5, ge=1, le=20)
    since_year: int = Field(default=2018, ge=1990, le=2030)


class VectorSearchRequest(BaseModel):
    """Request for semantic vector search."""
    query: str = Field(..., min_length=3, description="Semantic search query")
    target: str = Field(
        default="papers",
        description="papers | authors",
    )
    top_k: int = Field(default=10, ge=1, le=30)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    expand_query: bool = Field(default=True, description="Apply query expansion before embedding")


class SessionRequest(BaseModel):
    """Request to create or clear a conversation session."""
    session_id: str = Field(..., min_length=1, max_length=100)


class CacheControlRequest(BaseModel):
    """Admin cache management request."""
    action: str = Field(..., description="clear_all | get_stats")


# RESPONSE MODELS
class ValidationInfo(BaseModel):
    """Cypher validation details included in all graph query responses."""
    confidence_score: float
    issues: list[str]
    cypher_used: str
    retries: int


class PaginationInfo(BaseModel):
    """Pagination metadata for large result sets."""
    page: int
    page_size: int
    total_count: int
    has_more: bool


class QueryResponse(BaseModel):
    """Standard response for all /query requests."""
    answer: str = Field(..., description="Natural language answer from Gemini")
    query_type: str = Field(..., description="Pipeline used: GRAPH_TRAVERSAL | VECTOR_SIMILARITY | HYBRID | AGENT_COMPLEX | AMBIGUOUS | OUT_OF_DOMAIN")
    session_id: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    explanation: str = Field(default="", description="Plain English explanation of how the question was answered (bonus feature)")
    reasoning: str = Field(default="", description="The internal logic/pipeline used by the AI to arrive at the answer")
    validation: Optional[ValidationInfo] = None
    pagination: Optional[PaginationInfo] = None
    cached: bool = Field(default=False, description="True if this answer was served from cache")
    execution_time_ms: float = Field(default=0.0)
    agent_steps: list[dict[str, Any]] = Field(
        default_factory=list,
        description="ReAct agent reasoning trace (only for AGENT_COMPLEX queries)",
    )


class RecommendationResponse(BaseModel):
    """Response for recommendation requests."""
    answer: str
    papers: list[dict[str, Any]]
    strategy: str
    total: int
    explanation: str = ""


class VectorSearchResponse(BaseModel):
    """Response for vector search requests."""
    answer: str
    results: list[dict[str, Any]]
    scores: list[float]
    expanded_query: str
    total_found: int


class HealthResponse(BaseModel):
    """Server and Neo4j health status."""
    status: str
    neo4j: dict[str, Any]
    cache: dict[str, Any]
    version: str = "1.0.0"



class Message(BaseModel):
    """A single message in a conversation."""
    id: Optional[int] = None
    role: str
    content: str
    timestamp: Optional[str] = None

class SessionInfo(BaseModel):
    """Full details of a conversation session including messages."""
    session_id: str
    title: str
    turn_count: int
    history: list[Message] = Field(default_factory=list)


class SessionSummary(BaseModel):
    """Basic session metadata for the sidebar."""
    session_id: str
    title: str
    updated_at: str


class SessionListResponse(BaseModel):
    """List of all available sessions summary."""
    sessions: list[SessionSummary]


class ErrorResponse(BaseModel):
    """Standardised error response body."""
    error: str
    detail: str = ""
    status_code: int
