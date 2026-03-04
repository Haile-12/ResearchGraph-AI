from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",        
    )
    # Models
    gemini_api_key: str = Field(..., description="Google Gemini API key")
    google_api_key: str = Field(default="", description="Secondary Google API key (optional)")
    gemini_model: str = Field(..., description="LLM model name (e.g. gemini-1.5-flash)")
    gemini_embedding_model: str = Field(..., description="Local embedding model (e.g. all-mpnet-base-v2)")

    # Neo4j
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j Bolt URI (use neo4j+s:// for Aura cloud)",
    )
    neo4j_username: str = Field(default="neo4j")
    neo4j_password: str = Field(..., description="Neo4j password")
    neo4j_database: str = Field(
        default="neo4j",
        description="Target database name inside Neo4j",
    )

    # Application
    app_env: str = Field(default="development", description="development | production")
    log_level: str = Field(default="DEBUG")
    backend_port: int = Field(default=8000)
    frontend_port: int = Field(default=5173)

    # Cache 
    cache_max_size: int = Field(
        default=500,
        description="Maximum number of query results to keep in LRU cache",
    )
    cache_ttl_seconds: int = Field(
        default=1800,
        description="Time-to-live for cached entries (30 minutes default)",
    )

    # Query pipeline thresholds
    confidence_threshold: float = Field(
        default=0.7,
        description="Minimum Cypher confidence score required to execute a query",
    )
    correction_threshold: float = Field(
        default=0.4,
        description="Score below which we do NOT attempt auto-correction",
    )
    max_retry_attempts: int = Field(
        default=2,
        description="Number of times to retry a low-confidence query with correction",
    )

    # Vector search
    vector_similarity_threshold: float = Field(
        default=0.7,
        description="Minimum cosine similarity to include a vector search result",
    )
    vector_top_k: int = Field(
        default=10,
        description="Number of candidate nodes to retrieve from the vector index",
    )

    # Agent
    agent_max_iterations: int = Field(
        default=10,
        description="Safety cap on the ReAct agent iteration loop",
    )

    # Memory
    memory_buffer_k: int = Field(
        default=10,
        description="Number of conversation turns to keep in the memory buffer",
    )

    # Pagination
    pagination_default_page_size: int = Field(
        default=10,
        description="Default number of results per page for large result sets",
    )

    @property
    def is_development(self) -> bool:
        """Return True when running in development mode."""
        return self.app_env.lower() == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached singleton Settings instance.
    Uses lru_cache so the .env file is only parsed once per process.
    """
    return Settings()

settings: Settings = get_settings()
