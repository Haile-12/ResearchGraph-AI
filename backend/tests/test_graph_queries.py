import os
import sys
import pytest
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.query_validator import static_validate, validate_cypher
from utils.cypher_utils import (
    strip_markdown_fences,
    has_return_clause,
    has_write_operations,
    add_limit_if_missing,
    extract_node_labels,
    extract_relationship_types,
)
from config.settings import settings
from db.neo4j_client import get_schema_fallback

SCHEMA = get_schema_fallback()


# Cypher Utility Tests
class TestCypherUtils:
    """Tests for Cypher string manipulation utilities."""

    def test_strip_markdown_fences_cypher_block(self):
        """Should strip ```cypher ... ``` fences."""
        raw = "```cypher\nMATCH (n) RETURN n\n```"
        result = strip_markdown_fences(raw)
        assert result == "MATCH (n) RETURN n"

    def test_strip_markdown_fences_plain_block(self):
        """Should strip ``` ... ``` (no language tag)."""
        raw = "```\nMATCH (n) RETURN n\n```"
        result = strip_markdown_fences(raw)
        assert result == "MATCH (n) RETURN n"

    def test_no_fences_unchanged(self):
        """Queries without fences should be returned unchanged."""
        cypher = "MATCH (n:Paper) RETURN n.title"
        assert strip_markdown_fences(cypher) == cypher

    def test_has_return_clause_true(self):
        """RETURN keyword detection."""
        assert has_return_clause("MATCH (n) RETURN n") is True

    def test_has_return_clause_false(self):
        """Missing RETURN should return False."""
        assert has_return_clause("MATCH (n:Paper {title: 'GPT-3'})") is False

    def test_has_return_clause_case_insensitive(self):
        """Detection should be case-insensitive."""
        assert has_return_clause("MATCH (n) return n") is True

    def test_has_write_op_create(self):
        assert has_write_operations("CREATE (n:Paper) RETURN n") is True

    def test_has_write_op_delete(self):
        assert has_write_operations("MATCH (n) DELETE n") is True

    def test_has_write_op_set(self):
        assert has_write_operations("MATCH (n) SET n.name = 'test' RETURN n") is True

    def test_no_write_ops_read_query(self):
        assert has_write_operations("MATCH (n:Author) RETURN n.name") is False

    def test_add_limit_if_missing(self):
        """Should append LIMIT 20 when none exists."""
        cypher = "MATCH (n:Paper) RETURN n.title"
        result = add_limit_if_missing(cypher, limit=20)
        assert "LIMIT 20" in result

    def test_add_limit_not_duplicate(self):
        """Should not add LIMIT if one already exists."""
        cypher = "MATCH (n:Paper) RETURN n.title LIMIT 5"
        result = add_limit_if_missing(cypher, limit=20)
        assert result.count("LIMIT") == 1

    def test_extract_node_labels(self):
        """Should extract all node labels from MATCH patterns."""
        cypher = "MATCH (a:Author)-[:AUTHORED]->(p:Paper) RETURN a.name"
        labels = extract_node_labels(cypher)
        assert "Author" in labels
        assert "Paper" in labels

    def test_extract_relationship_types(self):
        """Should extract relationship type names."""
        cypher = "MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:CITES]->(c:Paper) RETURN *"
        rels = extract_relationship_types(cypher)
        assert "AUTHORED" in rels
        assert "CITES" in rels

# Common Graph Query Patterns
class TestCommonQueryPatterns:
    """Tests for queries that represent common user question types."""

    def test_who_authored_paper(self):
        """Standard 'who authored X' query should be valid."""
        cypher = """
        MATCH (a:Author)-[:AUTHORED]->(p:Paper)
        WHERE toLower(p.title) CONTAINS toLower('Attention Is All You Need')
        RETURN a.name AS author, p.year AS year
        ORDER BY p.year DESC
        """
        issues, deduction = static_validate(cypher)
        assert deduction < 0.3, f"Valid query has unexpected issues: {issues}"

    def test_papers_at_institution(self):
        """Find papers by authors at a given institution."""
        cypher = """
        MATCH (a:Author)-[:AFFILIATED_WITH]->(i:Institution {name: 'MIT'})
        MATCH (a)-[:AUTHORED]->(p:Paper)
        RETURN p.title, p.year, a.name
        ORDER BY p.year DESC
        LIMIT 10
        """
        issues, deduction = static_validate(cypher)
        assert deduction < 0.3, f"Institution query has issues: {issues}"

    def test_citation_chain_query(self):
        """Find papers that cite a specific paper."""
        cypher = """
        MATCH (citing:Paper)-[:CITES]->(cited:Paper)
        WHERE toLower(cited.title) CONTAINS 'adam'
        RETURN citing.title, citing.year
        ORDER BY citing.citations_count DESC
        LIMIT 10
        """
        issues, deduction = static_validate(cypher)
        assert deduction < 0.3, f"Citation query has issues: {issues}"

    def test_collaboration_query(self):
        """Find author collaboration network."""
        cypher = """
        MATCH (a:Author {name: 'Yann LeCun'})-[:COLLABORATED_WITH]-(collab:Author)
        WITH collab
        MATCH (collab)-[:AFFILIATED_WITH]->(i:Institution)
        RETURN collab.name, i.name AS institution, collab.h_index
        ORDER BY collab.h_index DESC
        LIMIT 10
        """
        issues, deduction = static_validate(cypher)
        assert deduction < 0.3, f"Collaboration query has issues: {issues}"

    def test_topic_hierarchy_query(self):
        """Navigate topic hierarchy via BELONGS_TO."""
        cypher = """
        MATCH (subtopic:Topic)-[:BELONGS_TO]->(parent:Topic {name: 'Deep Learning'})
        RETURN subtopic.name, subtopic.field
        ORDER BY subtopic.name
        """
        issues, deduction = static_validate(cypher)
        assert deduction < 0.3, f"Topic hierarchy query has issues: {issues}"

    def test_high_impact_papers_in_journal(self):
        """Find high citation papers published in a specific journal."""
        cypher = """
        MATCH (p:Paper)-[:PUBLISHED_IN]->(j:Journal {name: 'NeurIPS'})
        WHERE p.year >= 2017
        RETURN p.title, p.year, p.citations_count
        ORDER BY p.citations_count DESC
        LIMIT 5
        """
        issues, deduction = static_validate(cypher)
        assert deduction < 0.3, f"Journal query has issues: {issues}"

# Boundary and Edge Case Tests
class TestEdgeCases:
    """Tests for boundary conditions and edge cases in the pipeline."""

    def test_empty_question_handling(self):
        """Empty question string should not cause a crash in validation."""
        cypher = "MATCH (n) RETURN n"  # Valid query for empty-ish question
        result = validate_cypher(cypher, question="", schema=SCHEMA, use_llm=False)
        assert result is not None
        assert isinstance(result.confidence_score, float)

    def test_very_long_cypher_handled(self):
        """Extra-long Cypher should still be processable."""
        long_cypher = (
            "MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:COVERS_TOPIC]->(t:Topic)\n"
            "OPTIONAL MATCH (p)-[:CITES]->(cited:Paper)\n"
            "OPTIONAL MATCH (a)-[:AFFILIATED_WITH]->(i:Institution)\n"
            "OPTIONAL MATCH (p)-[:PUBLISHED_IN]->(j:Journal)\n"
            "WHERE p.year >= 2015 AND t.field = 'AI'\n"
            "RETURN p.title, p.year, a.name, t.name, j.name, "
            "collect(cited.title) AS citations\n"
            "ORDER BY p.citations_count DESC\n"
            "LIMIT 20"
        )
        issues, deduction = static_validate(long_cypher)
        assert deduction < 0.3, f"Complex valid query flagged: {issues}"

    def test_cypher_with_parameters(self):
        """Parametrized Cypher ($ placeholders) should validate without issues."""
        cypher = """
        MATCH (a:Author)-[:AUTHORED]->(p:Paper)
        WHERE toLower(a.name) CONTAINS toLower($author_name)
        RETURN p.title, p.year, p.citations_count
        ORDER BY p.citations_count DESC
        LIMIT $limit
        """
        issues, deduction = static_validate(cypher)
        assert deduction < 0.3, f"Parametrized query has unexpected issues: {issues}"

    def test_optional_match_valid(self):
        """OPTIONAL MATCH patterns should be accepted."""
        cypher = """
        MATCH (a:Author {name: 'Geoffrey Hinton'})
        OPTIONAL MATCH (a)-[:AFFILIATED_WITH]->(i:Institution)
        OPTIONAL MATCH (a)-[:AUTHORED]->(p:Paper)
        RETURN a.name, i.name, count(p) AS paper_count
        """
        issues, deduction = static_validate(cypher)
        assert deduction < 0.3, f"OPTIONAL MATCH query flagged: {issues}"

    def test_aggregation_query(self):
        """COUNT, COLLECT, and aggregation functions should be valid."""
        cypher = """
        MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:COVERS_TOPIC]->(t:Topic)
        RETURN t.name AS topic, count(p) AS paper_count, avg(p.citations_count) AS avg_citations
        ORDER BY paper_count DESC
        LIMIT 10
        """
        issues, deduction = static_validate(cypher)
        assert deduction < 0.3, f"Aggregation query has issues: {issues}"

# Graph Service Integration 
class TestGraphServiceMocked:
    """Tests for the graph service with mocked external calls."""

    @patch("services.graph_service.generate_text")
    @patch("services.graph_service.run_query")
    def test_graph_service_returns_result(self, mock_run_query, mock_generate):
        """Graph service should return a structured result."""
        from services.graph_service import run_graph_query
        mock_generate.return_value = (
            "MATCH (a:Author)-[:AUTHORED]->(p:Paper {title: 'GPT-3'}) RETURN a.name"
        )
        mock_run_query.return_value = [{"a.name": "Alec Radford"}, {"a.name": "Ilya Sutskever"}]

        result = run_graph_query("Who authored GPT-3?")
        assert result is not None
        assert isinstance(result.answer, str)
        assert len(result.answer) > 0

    @patch("services.graph_service.generate_text")
    @patch("services.graph_service.run_query")
    def test_empty_results_handled_gracefully(self, mock_run_query, mock_generate):
        """Empty Neo4j results should produce a helpful 'no results' message."""
        from services.graph_service import run_graph_query

        mock_generate.return_value = (
            "MATCH (a:Author)-[:AUTHORED]->(p:Paper {title: 'Nonexistent'}) RETURN a.name"
        )
        mock_run_query.return_value = []

        result = run_graph_query("Who authored Nonexistent Paper?")
        assert result is not None
        assert "no" in result.answer.lower() or "found" in result.answer.lower() or "ℹ" in result.answer
