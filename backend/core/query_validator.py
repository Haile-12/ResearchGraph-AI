from __future__ import annotations
import re
from dataclasses import dataclass, field
from config.prompts import CYPHER_VALIDATION_PROMPT
from config.settings import settings
from models.gemini_client import generate_json
from utils.logger import get_logger
logger = get_logger(__name__)

# Schema constants used by static validation (Matches Real Data)
VALID_NODE_LABELS = {"Paper", "Author", "Journal"}
VALID_RELATIONSHIP_TYPES = {
    "AUTHORED", "PUBLISHED_IN", "COLLABORATED_WITH"
}
VALID_PAPER_PROPS    = {"title", "abstract", "year", "citations_count", "doi", "embedding", "id"}
VALID_AUTHOR_PROPS   = {"name", "h_index", "email", "embedding", "id"}
VALID_JOURNAL_PROPS  = {"name", "id"}

# Relationship directions: (start_label, rel_type, end_label)
VALID_DIRECTIONS = {
    ("Author", "AUTHORED",        "Paper"),
    ("Paper",  "PUBLISHED_IN",    "Journal"),
    ("Author", "COLLABORATED_WITH", "Author"),
}

# Wrong directions that Gemini commonly produces
KNOWN_BAD_DIRECTIONS = {
    ("Paper",        "AUTHORED",        "Author"),
    ("Journal",      "PUBLISHED_IN",    "Paper"),
}

@dataclass
class ValidationResult:
    """Complete result of a validation pass."""
    confidence_score: float
    issues: list[str] = field(default_factory=list)
    corrected_cypher: str = ""
    is_executable: bool = False
    reasoning: str = ""

    @property
    def should_execute(self) -> bool:
        return self.confidence_score >= settings.confidence_threshold

    @property
    def should_attempt_correction(self) -> bool:
        return (
            settings.correction_threshold
            <= self.confidence_score
            < settings.confidence_threshold
        )

# Pass 1: Static / rule-based checks
def _check_has_return(cypher: str) -> list[str]:
    """Detect missing RETURN clause — a silent killer."""
    if not re.search(r"\bRETURN\b", cypher, re.IGNORECASE):
        return ["Missing RETURN clause — query returns nothing"]
    return []

def _check_node_labels(cypher: str) -> list[str]:
    """Detect node labels not in our schema."""
    # Extract labels from patterns like (variable:Label)
    found = re.findall(r"\([\w\s]*:(\w+)", cypher)
    issues = []
    for label in found:
        if label not in VALID_NODE_LABELS and label not in {
            "node", "n", "m", "a", "p", "t", "j", "i"
        }:
            issues.append(f"Unknown node label '{label}' (valid: {', '.join(sorted(VALID_NODE_LABELS))})")
    return issues

def _check_relationship_types(cypher: str) -> list[str]:
    """Detect relationship types not in the schema."""
    found = re.findall(r"\[:(\w+)", cypher)
    issues = []
    for rel in found:
        if rel not in VALID_RELATIONSHIP_TYPES:
            issues.append(
                f"Unknown relationship type ':{rel}' "
                f"(valid: {', '.join(sorted(VALID_RELATIONSHIP_TYPES))})"
            )
    return issues

def _check_write_operations(cypher: str) -> list[str]:
    """Detect destructive write operations that must never run."""
    write_keywords = re.findall(
        r"\b(CREATE|MERGE|DELETE|DETACH DELETE|SET|REMOVE|DROP)\b",
        cypher,
        re.IGNORECASE,
    )
    if write_keywords:
        return [f"Write operations not allowed: {', '.join(set(w.upper() for w in write_keywords))}"]
    return []

def _check_known_bad_directions(cypher: str) -> list[str]:
    # Match: (optvar:Label)-[:REL]->(optvar:Label)
    pattern = re.compile(
        r"\([\w\s]*:?(\w*)\)-\[:\s*(\w+)\s*\]->\([\w\s]*:?(\w*)\)",
        re.IGNORECASE,
    )
    issues = []
    for match in pattern.finditer(cypher):
        from_label = match.group(1).strip()
        rel_type   = match.group(2).strip().upper()
        to_label   = match.group(3).strip()

        # Check if this direction is explicitly known-bad
        for bad_from, bad_rel, bad_to in KNOWN_BAD_DIRECTIONS:
            if (
                bad_rel == rel_type
                and (not from_label or from_label == bad_from)
                and (not to_label or to_label == bad_to)
            ):
                issues.append(
                    f"Wrong direction for :{rel_type} — "
                    f"should be ({bad_to})-[:{rel_type}]->({bad_from}) "
                    f"but found ({from_label})-[:{rel_type}]->({to_label})"
                )
    return issues

def static_validate(cypher: str) -> tuple[list[str], float]:
    deductions = {
        "return":    0.5,
        "label":     0.3,
        "rel_type":  0.3,
        "direction": 0.4,
        "write":     1.0,
    }
    all_issues = []
    total_deduction = 0.0

    write_issues = _check_write_operations(cypher)
    if write_issues:
        return write_issues, 1.0  # Immediately fail

    return_issues = _check_has_return(cypher)
    all_issues.extend(return_issues)
    total_deduction += len(return_issues) * deductions["return"]

    label_issues = _check_node_labels(cypher)
    all_issues.extend(label_issues)
    total_deduction += len(label_issues) * deductions["label"]

    rel_issues = _check_relationship_types(cypher)
    all_issues.extend(rel_issues)
    total_deduction += len(rel_issues) * deductions["rel_type"]

    direction_issues = _check_known_bad_directions(cypher)
    all_issues.extend(direction_issues)
    total_deduction += len(direction_issues) * deductions["direction"]

    return all_issues, min(total_deduction, 1.0)

# Pass 2: LLM self-critique
def llm_validate(cypher: str, question: str, schema: str, static_score: float = 1.0) -> ValidationResult:
    prompt = CYPHER_VALIDATION_PROMPT.format(
        schema=schema,
        question=question,
        cypher=cypher,
    )
    try:
        result = generate_json(prompt)
    except (ValueError, Exception) as e:
        logger.warning("LLM validation failed, falling back to static score: %s", e)
        return ValidationResult(
            confidence_score=static_score,
            issues=["LLM validation unavailable — using static results"],
            corrected_cypher=cypher,
            is_executable=static_score >= settings.confidence_threshold,
            reasoning="LLM validation error — falling back to static analyzer",
        )

    score = float(result.get("confidence_score", 0.5))
    score = max(0.0, min(1.0, score))  # Clamp to [0, 1]

    return ValidationResult(
        confidence_score=score,
        issues=result.get("issues", []),
        corrected_cypher=result.get("corrected_cypher", cypher) or cypher,
        is_executable=result.get("is_executable", score >= settings.confidence_threshold),
        reasoning=result.get("reasoning", ""),
    )

# Combined validator 
def validate_cypher(
    cypher: str,
    question: str,
    schema: str,
    use_llm: bool = True,
) -> ValidationResult:
    # Pass 1: Static 
    static_issues, static_deduction = static_validate(cypher)
    static_score = 1.0 - static_deduction

    logger.debug(
        "Static validation: score=%.2f, issues=%d",
        static_score,
        len(static_issues),
    )

    # If static says refuse (< 0.4), don't bother calling the LLM
    if static_score < settings.correction_threshold:
        return ValidationResult(
            confidence_score=static_score,
            issues=static_issues,
            corrected_cypher=cypher,
            is_executable=False,
            reasoning="Static validation failed — multiple critical issues found",
        )

    if not use_llm:
        return ValidationResult(
            confidence_score=static_score,
            issues=static_issues,
            corrected_cypher=cypher,
            is_executable=static_score >= settings.confidence_threshold,
            reasoning="Static-only validation (LLM disabled)",
        )

    # Pass 2: LLM critique 
    llm_result = llm_validate(cypher, question, schema, static_score=static_score)

    # Use the corrected Cypher from LLM if it made corrections
    final_cypher = llm_result.corrected_cypher if llm_result.corrected_cypher else cypher

    # Final score = minimum of both passes
    final_score = min(static_score, llm_result.confidence_score)

    all_issues = static_issues + [
        issue for issue in llm_result.issues
        if issue not in static_issues  
    ]

    logger.info(
        "Validation complete: final_score=%.2f, issues=%d, executable=%s",
        final_score,
        len(all_issues),
        final_score >= settings.confidence_threshold,
    )

    return ValidationResult(
        confidence_score=final_score,
        issues=all_issues,
        corrected_cypher=final_cypher,
        is_executable=final_score >= settings.confidence_threshold,
        reasoning=llm_result.reasoning,
    )
