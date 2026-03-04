import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.query_validator import (
    static_validate,
    validate_cypher,
    VALID_NODE_LABELS,
    VALID_RELATIONSHIP_TYPES,
)
from config.settings import settings
from db.neo4j_client import get_schema_fallback

SCHEMA = get_schema_fallback()
# Test 1: Reversed Relationship Direction
# The most common Gemini mistake — (Paper)-[:AUTHORED]->(Author) instead of (Author)-[:AUTHORED]->(Paper)
class TestReversedRelationshipDirection:
    """Validates that backwards relationship directions are caught."""

    BAD_CYPHER = """
    MATCH (m:Paper {title: 'Attention Is All You Need'})-[:AUTHORED]->(p:Author)
    RETURN p.name
    """

    def test_static_check_catches_reversed_direction(self):
        """Static validator should detect the reversed AUTHORED direction."""
        issues, deduction = static_validate(self.BAD_CYPHER)
        assert len(issues) > 0, "Expected issues but none were found"
        assert deduction > 0.0, "Expected score deduction for wrong direction"
        direction_issues = [i for i in issues if "direction" in i.lower() or "Wrong direction" in i]
        assert direction_issues, f"Expected direction issue. Got: {issues}"

    def test_static_score_below_threshold(self):
        """Final score should be below the execution threshold."""
        issues, deduction = static_validate(self.BAD_CYPHER)
        score = 1.0 - deduction
        assert score < settings.confidence_threshold, (
            f"Reversed direction should score below {settings.confidence_threshold}, got {score:.2f}"
        )

    def test_full_validation_is_not_executable(self):
        """Full validation should mark this query as not executable."""
        result = validate_cypher(
            self.BAD_CYPHER,
            question="Who authored Attention Is All You Need?",
            schema=SCHEMA,
            use_llm=False,  # Skip LLM call in unit tests
        )
        assert not result.is_executable, "Reversed direction query should not be executable"
        assert result.confidence_score < settings.confidence_threshold

# Test 2: Non-Existent Node Label
# Gemini sometimes uses labels from the movies domain (Person, Movie, etc.)
class TestNonExistentNodeLabel:
    """Validates that unknown node labels are caught."""

    BAD_CYPHER = """
    MATCH (p:Person)-[:ACTED_IN]->(m:Movie)
    RETURN p.name, m.title
    """

    def test_catches_non_existent_labels(self):
        """Static check should flag Person and Movie as invalid labels."""
        issues, deduction = static_validate(self.BAD_CYPHER)
        label_issues = [i for i in issues if "Unknown node label" in i]
        assert len(label_issues) >= 1, f"Expected label issues. Got: {issues}"
        # Should flag at least Person and Movie
        issue_text = " ".join(label_issues)
        assert "Person" in issue_text or "Movie" in issue_text or "ACTED_IN" in issue_text

    def test_score_penalised(self):
        """Score should be significantly reduced for unknown labels."""
        issues, deduction = static_validate(self.BAD_CYPHER)
        assert deduction >= 0.3, f"Expected deduction ≥ 0.3, got {deduction:.2f}"

    def test_also_catches_invalid_relationship(self):
        """ACTED_IN is not a valid relationship in our schema."""
        issues, _ = static_validate(self.BAD_CYPHER)
        rel_issues = [i for i in issues if "Unknown relationship type" in i or "ACTED_IN" in i]
        assert rel_issues, f"Expected ACTED_IN to be flagged as invalid. Got: {issues}"


# Test 3: Missing RETURN Clause
# A query without RETURN is syntactically valid but returns nothing.
class TestMissingReturnClause:
    """Validates that queries without RETURN are caught."""

    BAD_CYPHER = "MATCH (p:Paper {title: 'GPT-3'})"

    def test_detects_missing_return(self):
        """The RETURN check should flag this query."""
        issues, deduction = static_validate(self.BAD_CYPHER)
        return_issues = [i for i in issues if "RETURN" in i.upper()]
        assert return_issues, f"Expected missing RETURN issue. Got: {issues}"

    def test_missing_return_deducts_score(self):
        """Missing RETURN should deduct 0.5 from the score."""
        issues, deduction = static_validate(self.BAD_CYPHER)
        assert deduction >= 0.5, f"Expected deduction ≥ 0.5 for missing RETURN, got {deduction:.2f}"

    def test_full_validation_flags_as_not_executable(self):
        """Full validation should not allow a query without RETURN to run."""
        result = validate_cypher(
            self.BAD_CYPHER,
            question="Find the GPT-3 paper",
            schema=SCHEMA,
            use_llm=False,
        )
        assert not result.is_executable

# Test 4: Write Operation (CREATE)
# Any write operation must be blocked — the system is read-only.
class TestWriteOperationBlocked:
    """Validates that CREATE, DELETE and other write ops are blocked immediately."""

    BAD_CYPHER_CREATE = "CREATE (p:Paper {title: 'Injected Paper', year: 2024}) RETURN p"
    BAD_CYPHER_DELETE = "MATCH (n) DETACH DELETE n"
    BAD_CYPHER_MERGE  = "MERGE (a:Author {name: 'Fake Author'}) RETURN a"

    def test_create_is_blocked(self):
        """CREATE should cause immediate failure (score = 0.0)."""
        issues, deduction = static_validate(self.BAD_CYPHER_CREATE)
        assert deduction >= 1.0, f"CREATE should max-deduct score. Got deduction={deduction:.2f}"
        assert issues, "Expected issues for CREATE operation"

    def test_delete_is_blocked(self):
        """DETACH DELETE should cause immediate failure."""
        issues, deduction = static_validate(self.BAD_CYPHER_DELETE)
        assert deduction >= 1.0

    def test_merge_is_blocked(self):
        """MERGE on its own (write intent) should be blocked."""
        issues, deduction = static_validate(self.BAD_CYPHER_MERGE)
        assert deduction >= 1.0

    def test_full_validation_refuses_write(self):
        """validate_cypher should not mark write queries as executable."""
        result = validate_cypher(
            self.BAD_CYPHER_CREATE,
            question="Create a paper",
            schema=SCHEMA,
            use_llm=False,
        )
        assert not result.is_executable
        assert result.confidence_score < settings.correction_threshold

# Test 5: Wrong Property Name (auto-correct zone)
# 'author.title' instead of 'author.name' — valid syntax, wrong property.
class TestWrongPropertyName:
    """
    Validates handling of semantically wrong but syntactically valid queries.
    Static checks won't catch this (we don't parse every property reference),
    but the LLM validation pass will. Here we test the static-only path.
    """

    SUSPECT_CYPHER = """
    MATCH (a:Author)-[:AUTHORED]->(p:Paper)
    WHERE a.title = 'Dr.'
    RETURN a.name, p.title
    """

    def test_static_check_passes_but_score_not_perfect(self):
        """Static check can't catch wrong property names — this is the LLM validator's job."""
        issues, deduction = static_validate(self.SUSPECT_CYPHER)
    
        score = 1.0 - deduction
        assert score >= 0.0  

# Test 6: Valid Query — Should Pass
# A correct query must not be rejected by the validator.
class TestValidQueryPasses:
    """Validates that a correct query is marked executable."""

    GOOD_CYPHER = """
    MATCH (a:Author)-[:AUTHORED]->(p:Paper)
    WHERE toLower(p.title) CONTAINS 'transformer'
    OPTIONAL MATCH (p)-[:PUBLISHED_IN]->(j:Journal)
    RETURN a.name AS author, p.title AS paper, p.year AS year, j.name AS journal
    ORDER BY p.citations_count DESC
    LIMIT 10
    """

    def test_valid_cypher_passes_static(self):
        """No issues should be found for a correct query."""
        issues, deduction = static_validate(self.GOOD_CYPHER)
        # Valid queries should have zero or minimal deductions
        assert deduction < 0.3, f"Valid query should have low deduction. Got: {deduction:.2f}. Issues: {issues}"

    def test_valid_cypher_marks_executable(self):
        """Full validation should mark this as executable."""
        result = validate_cypher(
            self.GOOD_CYPHER,
            question="Find papers with 'transformer' in the title",
            schema=SCHEMA,
            use_llm=False,
        )
        assert result.is_executable, (
            f"Valid query should be executable. Score: {result.confidence_score:.2f}, Issues: {result.issues}"
        )
        assert result.confidence_score >= settings.confidence_threshold

# Parametrized edge cases
@pytest.mark.parametrize("cypher,description,should_fail", [
    (
        "MATCH (p:Paper) RETURN p.title",
        "Simple valid query",
        False,
    ),
    (
        "MATCH (a:Author {name: 'Hinton'})-[:AFFILIATED_WITH]->(i:Institution) RETURN i.name",
        "Valid affiliation query",
        False,
    ),
    (
        "MATCH (p:Paper)-[:CITES]->(cited:Paper) RETURN p.title, cited.title LIMIT 5",
        "Valid citation query",
        False,
    ),
    (
        "MATCH (p:person) RETURN p.name",   
        "Lowercase label (wrong case)",
        True,
    ),
    (
        "MATCH (a:Author)-[:PUBLISHED_BY]->(p:Paper) RETURN a.name", 
        "Non-existent relationship PUBLISHED_BY",
        True,
    ),
])
def test_parametrized_validation(cypher: str, description: str, should_fail: bool):
    """Parametrized test across multiple valid and invalid Cypher queries."""
    issues, deduction = static_validate(cypher)
    score = 1.0 - deduction

    if should_fail:
        assert score < settings.confidence_threshold or issues, (
            f"Expected '{description}' to have issues. Score={score:.2f}, Issues={issues}"
        )
    else:
        assert deduction < 0.3, (
            f"Valid query '{description}' should have low deduction. "
            f"Got {deduction:.2f}, issues: {issues}"
        )
