from __future__ import annotations
import threading
from contextlib import contextmanager
from typing import Any, Generator
from neo4j import GraphDatabase, Driver, Session, Result
from neo4j.exceptions import ServiceUnavailable
from config.settings import settings
from utils.logger import get_logger
logger = get_logger(__name__)

# Thread-safe singleton driver
_driver_lock = threading.Lock()
_driver_instance: Driver | None = None

# Cache the schema string so we don't re-query on every LLM call
_schema_cache: str | None = None

def get_driver() -> Driver:
    global _driver_instance
    if _driver_instance is None:
        with _driver_lock:
            # Double-checked locking pattern
            if _driver_instance is None:
                logger.info(
                    "Creating Neo4j driver → %s (db=%s)",
                    settings.neo4j_uri,
                    settings.neo4j_database,
                )
                _driver_instance = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_username, settings.neo4j_password),
                    max_connection_pool_size=50,
                    connection_timeout=30,
                )
    return _driver_instance

def close_driver() -> None:
    """Close the driver — call this on application shutdown."""
    global _driver_instance
    if _driver_instance is not None:
        _driver_instance.close()
        _driver_instance = None
        logger.info("Neo4j driver closed")

@contextmanager
def get_session() -> Generator[Session, None, None]:
    driver = get_driver()
    session = driver.session(database=settings.neo4j_database)
    try:
        yield session
    finally:
        session.close()


def run_query(cypher: str, parameters: dict[str, Any] | None = None) -> list[dict]:
    params = parameters or {}
    logger.debug("Running Cypher: %s | params=%s", cypher.strip()[:120], params)

    with get_session() as session:
        result: Result = session.run(cypher, params)
        records = [dict(record) for record in result]

    logger.debug("Query returned %d records", len(records))
    return records

def health_check() -> dict[str, Any]:
    try:
        records = run_query("CALL dbms.components() YIELD name, versions RETURN name, versions")
        count_result = run_query("MATCH (n) RETURN count(n) AS node_count")
        return {
            "status": "connected",
            "server": records[0] if records else {},
            "node_count": count_result[0].get("node_count", 0) if count_result else 0,
        }
    except (ServiceUnavailable, Exception) as exc:
        logger.error("Neo4j health check failed: %s", exc)
        return {"status": "unreachable", "error": str(exc)}

def get_schema() -> str:
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache

    logger.info("Fetching Neo4j schema (will be cached)")

    # Node labels and their properties 
    node_rows = run_query(
        """
        CALL apoc.meta.nodeTypeProperties()
        YIELD nodeType, propertyName, propertyTypes
        RETURN nodeType, propertyName, propertyTypes
        ORDER BY nodeType, propertyName
        """
    )

    # Relationship types 
    rel_rows = run_query(
        """
        CALL apoc.meta.relTypeProperties()
        YIELD relType, propertyName, propertyTypes
        RETURN relType, propertyName, propertyTypes
        ORDER BY relType
        """
    )

    # Build a human-readable schema string
    lines = ["=== Neo4j Schema ===\n", "Node Types and Properties:"]
    current_node = None
    for row in node_rows:
        node = row.get("nodeType", "")
        prop = row.get("propertyName", "")
        types = row.get("propertyTypes", [])
        if node != current_node:
            lines.append(f"\n  {node}:")
            current_node = node
        if prop:
            lines.append(f"    - {prop}: {', '.join(types) if types else 'unknown'}")

    lines.append("\nRelationship Types:")
    for row in rel_rows:
        rel = row.get("relType", "")
        prop = row.get("propertyName", "")
        types = row.get("propertyTypes", [])
        if prop:
            lines.append(f"  {rel}: {prop} ({', '.join(types) if types else 'unknown'})")
        else:
            lines.append(f"  {rel}")

    _schema_cache = "\n".join(lines)
    return _schema_cache

def get_schema_fallback() -> str:
    return """
=== Academic Research Knowledge Graph Schema ===

Node Labels and Properties:
  Paper:       title (str), abstract (str), year (int), citations_count (int), doi (str), embedding (list)
  Author:      name (str), h_index (int), birth_year (int), email (str), embedding (list)
  Institution: name (str), country (str), type (str: 'university'|'research_lab'|'industry')
  Topic:       name (str), description (str), field (str)
  Journal:     name (str), impact_factor (float), issn (str)

Relationship Types and Directions:
  (Author)-[:AUTHORED {contribution_type}]->(Paper)
  (Paper)-[:CITES {year_cited}]->(Paper)
  (Author)-[:AFFILIATED_WITH {start_year, end_year}]->(Institution)
  (Paper)-[:COVERS_TOPIC {relevance_score}]->(Topic)
  (Paper)-[:PUBLISHED_IN {volume, issue, year}]->(Journal)
  (Author)-[:COLLABORATED_WITH {paper_count}]->(Author)
  (Topic)-[:BELONGS_TO]->(Topic)
"""

# Convenience singleton imported elsewhere
neo4j_client = {
    "run_query": run_query,
    "get_schema": get_schema_fallback, 
    "health_check": health_check,
}
