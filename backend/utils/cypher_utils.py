from __future__ import annotations
import re
def strip_markdown_fences(cypher: str) -> str:
    """
    Remove markdown code fences that Gemini sometimes wraps around Cypher.
    """
    cypher = re.sub(r"^```(?:cypher|neo4j|sql)?\s*", "", cypher.strip(), flags=re.IGNORECASE)
    cypher = re.sub(r"\s*```$", "", cypher.strip())
    cypher = cypher.strip("`").strip()
    return cypher


def normalize_cypher_whitespace(cypher: str) -> str:
    return " ".join(cypher.split())

def extract_node_labels(cypher: str) -> list[str]:
    labels = re.findall(r"\([\w\s]*:(\w+)", cypher)
    return list(set(labels))

def extract_relationship_types(cypher: str) -> list[str]:
    types = re.findall(r"\[[\w\s]*:(\w+)", cypher)
    return list(set(types))

def has_return_clause(cypher: str) -> bool:
    return bool(re.search(r"\bRETURN\b", cypher, re.IGNORECASE))


def has_write_operations(cypher: str) -> bool:
    write_keywords = r"\b(CREATE|MERGE|DELETE|DETACH DELETE|SET|REMOVE|DROP)\b"
    return bool(re.search(write_keywords, cypher, re.IGNORECASE))


def add_limit_if_missing(cypher: str, limit: int = 20) -> str:
    if not re.search(r"\bLIMIT\b", cypher, re.IGNORECASE):
        cypher = cypher.rstrip().rstrip(";")
        cypher += f"\nLIMIT {limit}"
    return cypher


def fix_common_case_errors(cypher: str) -> str:
    keywords = [
        "match", "return", "where", "with", "optional", "order by",
        "limit", "skip", "unwind", "call", "yield", "merge", "create",
        "delete", "set", "remove",
    ]
    for kw in keywords:
        cypher = re.sub(
            rf"\b{kw}\b",
            kw.upper(),
            cypher,
            flags=re.IGNORECASE,
        )

    # Fix common label case errors
    label_corrections = {
        r"\bpaper\b":       "Paper",
        r"\bauthor\b":      "Author",
        r"\binstitution\b": "Institution",
        r"\btopic\b":       "Topic",
        r"\bjournal\b":     "Journal",
        # Catch wrong names from movies domain leaking through
        r"\bperson\b":      "Author",
        r"\bmovie\b":       "Paper",
    }
    for pattern, replacement in label_corrections.items():
        # Only replace when it looks like a node label (preceded by : or ( )
        cypher = re.sub(
            r"(?<=[:(\s])" + pattern,
            replacement,
            cypher,
        )

    return cypher

def format_cypher_for_display(cypher: str) -> str:
    keywords = ["MATCH", "OPTIONAL MATCH", "WHERE", "WITH", "RETURN",
                "ORDER BY", "LIMIT", "SKIP", "CALL", "YIELD", "UNWIND"]
    result = cypher.strip()
    for kw in keywords:
        result = re.sub(rf"\s+{kw}\b", f"\n{kw}", result, flags=re.IGNORECASE)
    return result.strip()
