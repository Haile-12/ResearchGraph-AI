from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from config.prompts import CYPHER_GENERATION_PROMPT
from config.settings import settings
from core.query_executor import ExecutionResult, execute_cypher
from core.query_validator import ValidationResult, validate_cypher
from core.response_formatter import format_response, generate_query_explanation
from db.neo4j_client import get_schema_fallback
from models.gemini_client import generate_text
from utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class GraphServiceResult:
    """Complete result from the graph traversal pipeline."""
    answer: str
    cypher_used: str
    confidence_score: float
    explanation: str
    records: list[dict[str, Any]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    retries: int = 0
    execution_time_ms: float = 0.0
    total_count: int = 0
    has_more: bool = False
    page: int = 1
    error: str | None = None

def run_graph_query(
    question: str,
    conversation_history: str = "",
    page: int = 1,
    page_size: int | None = None,
) -> GraphServiceResult:
    schema = get_schema_fallback()
    retries = 0
    last_validation: ValidationResult | None = None
    cypher = ""
    # Retry loop: generate → validate → (correct if needed) → repeat
    for attempt in range(settings.max_retry_attempts + 1):
        # Step 1: Generate Cypher
        if attempt == 0:
            cypher = _generate_cypher(question, schema, conversation_history)
        else:
            # Auto-correction: inject the issues into a new generation prompt
            cypher = _generate_corrected_cypher(
                question, schema, conversation_history,
                original_cypher=cypher,
                issues=last_validation.issues if last_validation else [],
            )
            retries += 1
            logger.info("Retry %d/%d with corrected Cypher", retries, settings.max_retry_attempts)

        # Step 2: Validate
        validation = validate_cypher(cypher, question, schema)
        last_validation = validation

        logger.info(
            "Validation attempt %d: score=%.2f, executable=%s",
            attempt + 1,
            validation.confidence_score,
            validation.is_executable,
        )

        if validation.is_executable:
            # Use corrected Cypher if validator improved it
            cypher = validation.corrected_cypher or cypher
            break

        if not validation.should_attempt_correction:
            # Score below correction threshold — stop retrying
            logger.warning(
                "Confidence %.2f below correction threshold %.2f — refusing query",
                validation.confidence_score,
                settings.correction_threshold,
            )
            return GraphServiceResult(
                answer=(
                    "I couldn't generate a reliable query for your question. "
                    f"Issues found:\n" +
                    "\n".join(f"• {issue}" for issue in validation.issues) +
                    "\n\nPlease rephrase your question or be more specific."
                ),
                cypher_used=cypher,
                confidence_score=validation.confidence_score,
                explanation="Query validation failed — score below minimum threshold",
                issues=validation.issues,
                retries=retries,
                error="Low confidence score",
            )

    # If exhausted retries without reaching the threshold
    if last_validation and not last_validation.is_executable:
        return GraphServiceResult(
            answer=(
                "I attempted to correct the query but could not reach "
                "sufficient confidence. Please try rephrasing your question."
            ),
            cypher_used=cypher,
            confidence_score=last_validation.confidence_score,
            explanation="Exhausted retry attempts without reaching confidence threshold",
            issues=last_validation.issues or [],
            retries=retries,
            error="Retry limit reached",
        )

    # Step 3: Execute
    exec_result: ExecutionResult = execute_cypher(
        cypher,
        page=page,
        page_size=page_size,
    )

    if not exec_result.success:
        return GraphServiceResult(
            answer=f"Database error: {exec_result.error}",
            cypher_used=cypher,
            confidence_score=last_validation.confidence_score if last_validation else 0.0,
            explanation="Query execution failed",
            issues=[exec_result.error or "Unknown execution error"],
            retries=retries,
            error=exec_result.error,
        )

    # Step 4: Humanize results
    formatted = format_response(
        question=question,
        results=exec_result.records,
        query_type="GRAPH_TRAVERSAL",
        conversation_history=conversation_history,
        confidence_score=last_validation.confidence_score if last_validation else 1.0,
    )
    answer = formatted["answer"]
    reasoning = formatted["reasoning"]

    # Step 5: Generate explanation
    explanation = generate_query_explanation(question, cypher, "GRAPH_TRAVERSAL")

    return GraphServiceResult(
        answer=answer,
        cypher_used=cypher,
        confidence_score=last_validation.confidence_score if last_validation else 1.0,
        explanation=explanation,
        records=exec_result.records,
        issues=last_validation.issues if last_validation else [],
        retries=retries,
        execution_time_ms=exec_result.execution_time_ms,
        total_count=exec_result.total_count,
        has_more=exec_result.has_more,
        page=exec_result.page,
    )

# Private helpers
def _generate_cypher(
    question: str,
    schema: str,
    conversation_history: str,
) -> str:
    """Call Gemini to generate a Cypher query from the natural language question."""
    prompt = CYPHER_GENERATION_PROMPT.format(
        schema=schema,
        question=question,
        conversation_history=conversation_history or "No prior conversation",
    )
    cypher = generate_text(prompt, temperature=0.0)
    cypher = cypher.strip().lstrip("```cypher").lstrip("```").rstrip("```").strip()
    logger.debug("Generated Cypher: %s", cypher[:300])
    return cypher

def _generate_corrected_cypher(
    question: str,
    schema: str,
    conversation_history: str,
    original_cypher: str,
    issues: list[str],
) -> str:
    """Generate a corrected Cypher by telling Gemini what was wrong."""
    issues_text = "\n".join(f"- {issue}" for issue in issues) if issues else "- Unknown issues"
    correction_prompt = f"""
The following Cypher query has issues that need to be fixed:

Original question: {question}

Problematic Cypher:
{original_cypher}

Issues found:
{issues_text}

Database schema:
{schema}

Write a CORRECTED Cypher query that fixes ALL the above issues.
Return ONLY the corrected Cypher query, no explanation, no markdown.
"""
    corrected = generate_text(correction_prompt, temperature=0.0)
    corrected = corrected.strip().lstrip("```cypher").lstrip("```").rstrip("```").strip()
    logger.debug("Corrected Cypher: %s", corrected[:300])
    return corrected
