from __future__ import annotations
from config.prompts import (
    RESPONSE_HUMANIZATION_PROMPT,
    QUERY_EXPLANATION_PROMPT,
    RECOMMENDATION_EXPLANATION_PROMPT,
)
from models.gemini_client import generate_text, generate_with_high_creativity
from utils.logger import get_logger

logger = get_logger(__name__)

def format_response(
    question: str,
    results: list[dict],
    query_type: str,
    conversation_history: str = "",
    confidence_score: float = 1.0,
) -> dict[str, str]:
    if not results:
        empty_answer = _handle_empty_results(question, query_type)
        return {
            "answer": empty_answer,
            "reasoning": f"Zero results found for {query_type} query."
        }

    # Limit records sent to Gemini to avoid token overflow
    preview_records = results[:20] if isinstance(results, list) else []
    
    prompt = RESPONSE_HUMANIZATION_PROMPT.format(
        question=question,
        results=_serialize_results(preview_records),
        query_type=query_type,
        confidence_score=f"{confidence_score:.2f}",
        conversation_history=conversation_history or "No prior conversation",
    )

    try:
        raw_output = generate_text(prompt, temperature=0.3, max_tokens=2048)
        logger.debug("Response formatted (%d chars)", len(raw_output))
        
        # Parse the structured sections
        reasoning = ""
        answer = raw_output
        
        if "---REASONING---" in raw_output and "---ANSWER---" in raw_output:
            parts = raw_output.split("---ANSWER---")
            answer = parts[1].strip()
            reasoning = parts[0].replace("---REASONING---", "").strip()
        elif "---REASONING---" in raw_output:
            reasoning = raw_output.replace("---REASONING---", "").strip()
            answer = "See reasoning above for findings."

        return {
            "answer": answer,
            "reasoning": reasoning
        }
    except Exception as e:
        logger.error("Response formatting failed: %s", e)
        return {
            "answer": _fallback_format(results),
            "reasoning": f"Formatting error: {str(e)}"
        }

def generate_query_explanation(
    question: str,
    cypher: str,
    query_type: str,
) -> str:
    prompt = QUERY_EXPLANATION_PROMPT.format(
        question=question,
        cypher=cypher,
        query_type=query_type,
    )
    try:
        return generate_text(prompt, temperature=0.2, max_tokens=512)
    except Exception as e:
        logger.warning("Explanation generation failed: %s", e)
        return f"Used {query_type.replace('_', ' ').lower()} to answer your question."


def format_recommendation_response(
    query: str,
    items: list[dict],
    scores: list[float],
) -> str:
    if not items:
        return (
            "I couldn't find papers that closely match your query. "
            "Try using different keywords or a broader description of the research area."
        )

    prompt = RECOMMENDATION_EXPLANATION_PROMPT.format(
        query=query,
        items=_serialize_results(items[:10]),
        scores=[f"{s:.3f}" for s in scores[:10]],
    )
    try:
        return generate_with_high_creativity(prompt, max_tokens=1536)
    except Exception as e:
        logger.warning("Recommendation formatting failed: %s", e)
        return _format_items_as_list(items, scores)

# Private helpers
def _handle_empty_results(question: str, query_type: str) -> str:
    """Return a helpful message when no results are found."""
    hints = {
        "GRAPH_TRAVERSAL": (
            "No records matched your query. "
            "Try checking the spelling of names, titles, or institutions."
        ),
        "VECTOR_SIMILARITY": (
            "No papers were found with sufficient semantic similarity (threshold: 0.7). "
            "Try a broader description or different keywords."
        ),
        "HYBRID": (
            "The combined filters returned no results. "
            "Try relaxing either the semantic or graph constraints."
        ),
        "AGENT_COMPLEX": (
            "The multi-step analysis returned no conclusive results. "
            "This may be due to missing data in the current dataset."
        ),
    }
    base = hints.get(query_type, "No results found for your query.")
    return f" {base}\n\nYour question: *{question}*"


def _serialize_results(results: list[dict]) -> str:
    if not results:
        return "No specific data records were found in the database."

    serialized = []
    preview = results[:20] if isinstance(results, list) else []
    for i, res in enumerate(preview, 1):
        record_lines = [f"Record {i}:"]
        for k, v in res.items():
            val_str = str(v)
            if len(val_str) > 3000:
                val_str = val_str[:3000] + "..."
            record_lines.append(f"  {k}: {val_str}")
        serialized.append("\n".join(record_lines))

    return "\n\n".join(serialized)

def _fallback_format(records: list[dict]) -> str:
    lines = ["**Results:**\n"]
    preview = records[:15] if isinstance(records, list) else []
    for i, record in enumerate(preview, 1):
        row = " | ".join(f"{k}: {v}" for k, v in record.items() if v is not None)
        lines.append(f"{i}. {row}")
    if len(records) > 15:
        lines.append(f"\n*...and {len(records) - 15} more results.*")
    return "\n".join(lines)

def _format_items_as_list(items: list[dict], scores: list[float]) -> str:
    lines = ["**Recommended Papers:**\n"]
    for item, score in zip(items[:10], scores[:10]):
        title = item.get("paper.title", item.get("title", "Unknown"))
        year  = item.get("paper.year", item.get("year", ""))
        lines.append(f"- **{title}** ({year}) — similarity: {score:.2f}")
    return "\n".join(lines)
