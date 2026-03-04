import os
import pytest
os.environ.setdefault("GEMINI_API_KEY",   "fake-test-key-for-ci")
os.environ.setdefault("NEO4J_PASSWORD",   "fake-password")
os.environ.setdefault("NEO4J_URI",        "bolt://localhost:7687")
os.environ.setdefault("APP_ENV",          "test")
os.environ.setdefault("LOG_LEVEL",        "ERROR")  

# Shared fixtures
@pytest.fixture(scope="session")
def sample_papers():
    """A small list of paper dicts matching our Neo4j schema."""
    return [
        {
            "title": "Attention Is All You Need",
            "year": 2017,
            "citations_count": 90000,
            "abstract": "We propose the Transformer architecture based solely on attention mechanisms.",
            "authors": ["Vaswani, A.", "Shazeer, N."],
            "topics": ["Deep Learning", "NLP"],
            "journal": "NeurIPS",
            "score": 0.98,
        },
        {
            "title": "BERT: Pre-training of Deep Bidirectional Transformers",
            "year": 2019,
            "citations_count": 65000,
            "abstract": "We introduce BERT, which stands for Bidirectional Encoder Representations.",
            "authors": ["Devlin, J.", "Chang, M."],
            "topics": ["NLP", "Language Models"],
            "journal": "NAACL",
            "score": 0.91,
        },
        {
            "title": "Generative Adversarial Networks",
            "year": 2014,
            "citations_count": 75000,
            "abstract": "We propose a framework for estimating generative models via adversarial training.",
            "authors": ["Goodfellow, I.", "Bengio, Y."],
            "topics": ["Generative AI", "Deep Learning"],
            "journal": "NeurIPS",
            "score": 0.87,
        },
    ]


@pytest.fixture(scope="session")
def sample_authors():
    """A small list of author dicts matching our Neo4j schema."""
    return [
        {"name": "Geoffrey Hinton",    "h_index": 156, "institution": "University of Toronto"},
        {"name": "Yann LeCun",         "h_index": 143, "institution": "NYU"},
        {"name": "Yoshua Bengio",      "h_index": 182, "institution": "Université de Montréal"},
        {"name": "Andrej Karpathy",    "h_index":  72, "institution": "Stanford University"},
    ]


@pytest.fixture
def valid_cypher_queries():
    """List of Cypher queries that should pass static validation."""
    return [
        "MATCH (a:Author)-[:AUTHORED]->(p:Paper) RETURN a.name, p.title LIMIT 10",
        "MATCH (p:Paper)-[:CITES]->(c:Paper) RETURN p.title, c.title LIMIT 5",
        "MATCH (a:Author)-[:AFFILIATED_WITH]->(i:Institution) RETURN a.name, i.name LIMIT 10",
        "MATCH (p:Paper)-[:COVERS_TOPIC]->(t:Topic) WHERE t.name = 'Deep Learning' RETURN p.title LIMIT 10",
        "MATCH (p:Paper)-[:PUBLISHED_IN]->(j:Journal) RETURN j.name, count(p) AS count ORDER BY count DESC",
    ]


@pytest.fixture
def invalid_cypher_queries():
    """List of Cypher queries that should FAIL static validation."""
    return [
        "MATCH (p:Paper)-[:AUTHORED]->(a:Author) RETURN a.name",  # Reversed direction
        "MATCH (p:Person)-[:ACTED_IN]->(m:Movie) RETURN p.name",  # Wrong domain labels
        "MATCH (p:Paper {title: 'GPT-3'})",                       # Missing RETURN
        "CREATE (n:Paper {title: 'Test'}) RETURN n",              # Write operation
        "MERGE (a:Author {name: 'Test'}) RETURN a",               # Write operation
    ]
