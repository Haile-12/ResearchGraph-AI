from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any

from neo4j.exceptions import CypherSyntaxError, CypherTypeError, ClientError

from config.settings import settings
from db.neo4j_client import run_query
from utils.logger import get_logger

logger = get_logger(__name__)

# Threshold for logging a query as "slow" (seconds)
SLOW_QUERY_THRESHOLD_SEC = 3.0


@dataclass
class ExecutionResult:
    """Encapsulates query execution outcome."""
    success: bool
    records: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    execution_time_ms: float = 0.0
    total_count: int = 0       
    page: int = 1
    page_size: int = 0
    has_more: bool = False     


def execute_cypher(
    cypher: str,
    parameters: dict[str, Any] | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> ExecutionResult:
    if page_size is None:
        page_size = settings.pagination_default_page_size

    params = parameters or {}
    start = time.perf_counter()

    try:
        raw_records = run_query(cypher, params)
    except CypherSyntaxError as e:
        logger.error("Cypher syntax error: %s\nQuery: %s", e, cypher)
        return ExecutionResult(
            success=False,
            error=f"Query syntax error: {str(e)[:200]}",
        )
    except CypherTypeError as e:
        logger.error("Cypher type error: %s\nQuery: %s", e, cypher)
        return ExecutionResult(
            success=False,
            error=f"Query type error: {str(e)[:200]}",
        )
    except ClientError as e:
        logger.error("Neo4j client error: %s\nQuery: %s", e, cypher)
        return ExecutionResult(
            success=False,
            error=f"Database error: {e.code} — {str(e)[:200]}",
        )
    except Exception as e:
        logger.exception("Unexpected execution error: %s", e)
        return ExecutionResult(
            success=False,
            error=f"Unexpected error: {str(e)[:200]}",
        )

    elapsed_ms = (time.perf_counter() - start) * 1000

    # Log slow queries so we can optimise indexes
    if elapsed_ms > SLOW_QUERY_THRESHOLD_SEC * 1000:
        logger.warning(
            "SLOW QUERY (%.0fms): %s",
            elapsed_ms,
            cypher.strip()[:150],
        )
    else:
        logger.debug("Query executed in %.0fms, %d records", elapsed_ms, len(raw_records))

    # Pagination
    total_count = len(raw_records)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated = raw_records[start_idx:end_idx]
    has_more = end_idx < total_count

    return ExecutionResult(
        success=True,
        records=paginated,
        execution_time_ms=elapsed_ms,
        total_count=total_count,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


def execute_raw(cypher: str, parameters: dict[str, Any] | None = None) -> list[dict]:
    """
    Execute without pagination — used internally by agent tools
    where the agent needs the full result set for reasoning.
    """
    try:
        return run_query(cypher, parameters or {})
    except Exception as e:
        logger.error("Raw execution error: %s", e)
        return []
