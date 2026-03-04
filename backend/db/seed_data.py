import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.neo4j_client import run_query, close_driver
from models.embeddings import generate_embedding
from utils.logger import get_logger
import json

logger = get_logger(__name__)

REAL_DATA_FILE = "real_research_data.json"

def load_real_data():
    """Load and return the real research data from JSON."""
    if not os.path.exists(REAL_DATA_FILE):
        logger.error(f"Real data file {REAL_DATA_FILE} not found!")
        sys.exit(1)
    
    with open(REAL_DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        logger.info(f"Loaded {len(data.get('PAPERS', []))} papers and {len(data.get('AUTHORS', []))} authors.")
        return data

def clear_database() -> None:
    """Remove all nodes and relationships before seeding."""
    logger.warning("Clearing all data from Neo4j database...")
    run_query("MATCH (n) DETACH DELETE n")
    logger.info("Database cleared")

def create_constraints() -> None:
    """Create uniqueness constraints for data integrity."""
    constraints = [
        "CREATE CONSTRAINT paper_id IF NOT EXISTS FOR (p:Paper) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT author_id IF NOT EXISTS FOR (a:Author) REQUIRE a.id IS UNIQUE",
        "CREATE CONSTRAINT journal_id IF NOT EXISTS FOR (j:Journal) REQUIRE j.id IS UNIQUE",
    ]
    for constraint in constraints:
        try:
            run_query(constraint)
        except Exception as e:
            logger.debug("Constraint may already exist: %s", e)
    logger.info("Constraints created")

def create_vector_indexes() -> None:
    """Create vector indexes for semantic similarity search."""
    indexes = [
        """
        CREATE VECTOR INDEX paper_embeddings IF NOT EXISTS
        FOR (p:Paper) ON p.embedding
        OPTIONS {
            indexConfig: {
                `vector.dimensions`: 768,
                `vector.similarity_function`: 'cosine'
            }
        }
        """,
        """
        CREATE VECTOR INDEX author_embeddings IF NOT EXISTS
        FOR (a:Author) ON a.embedding
        OPTIONS {
            indexConfig: {
                `vector.dimensions`: 768,
                `vector.similarity_function`: 'cosine'
            }
        }
        """,
    ]
    for index_cypher in indexes:
        try:
            run_query(index_cypher)
            logger.info("Vector index created/verified")
        except Exception as e:
            logger.warning("Vector index creation warning: %s", e)

def seed_authors(authors):
    """Insert Real Author nodes."""
    for author in authors:
        # Build embedding from name
        embed_text = f"Author: {author['name']}. Expertise: Research, Academic Publications."
        try:
            embedding = generate_embedding(embed_text)
        except Exception as e:
            logger.warning("Could not generate embedding for author %s: %s", author['name'], e)
            embedding = [0.0] * 768

        run_query(
            """
            MERGE (a:Author {id: $id})
            SET a.name = $name, a.h_index = $h_index, a.email = $email,
                a.embedding = $embedding
            """,
            {
                "id": str(author['id']),
                "name": author['name'],
                "h_index": author.get('h_index', 0),
                "email": author.get('email', ""),
                "embedding": embedding
            }
        )
    logger.info(f"Seeded {len(authors)} authors.")

def seed_papers(papers):
    """Insert Real Paper nodes and Journals."""
    for paper in papers:
        # Generate embedding
        embed_text = f"Title: {paper['title']}. Abstract: {paper['abstract']}"
        try:
            embedding = generate_embedding(embed_text)
        except Exception as e:
            logger.warning("Could not generate embedding for paper %s: %s", paper['id'], e)
            embedding = [0.0] * 768

        run_query(
            """
            MERGE (p:Paper {id: $id})
            SET p.title = $title, p.abstract = $abstract,
                p.year = $year, p.citations_count = $citations_count,
                p.doi = $doi, p.embedding = $embedding
            """,
            {
                "id": str(paper['id']),
                "title": paper['title'],
                "abstract": paper['abstract'],
                "year": paper.get('year', 2024),
                "citations_count": paper.get('citations_count', 0),
                "doi": paper.get('doi', ""),
                "embedding": embedding
            }
        )

        # Journal node (if exists)
        journal_name = paper.get('journal_name')
        if journal_name:
            # Create a unique ID for the journal
            j_id = "j_" + journal_name.lower().replace(" ", "_")
            run_query(
                """
                MERGE (j:Journal {id: $j_id})
                SET j.name = $name
                WITH j
                MATCH (p:Paper {id: $p_id})
                MERGE (p)-[:PUBLISHED_IN]->(j)
                """,
                {"j_id": j_id, "name": journal_name, "p_id": str(paper['id'])}
            )

        # Author relationships
        for author_id in paper.get("authors", []):
            run_query(
                """
                MATCH (a:Author {id: $author_id}), (p:Paper {id: $paper_id})
                MERGE (a)-[:AUTHORED]->(p)
                """,
                {"author_id": str(author_id), "paper_id": str(paper['id'])}
            )

    logger.info(f"Seeded {len(papers)} papers.")

def seed_collaborations(papers):
    """Derive COLLABORATED_WITH from common paper authorship."""
    for paper in papers:
        authors = paper.get("authors", [])
        if len(authors) > 1:
            for i, auth_a in enumerate(authors):
                for auth_b in authors[i+1:]:
                    run_query(
                        """
                        MATCH (a:Author {id: $id_a}), (b:Author {id: $id_b})
                        MERGE (a)-[r:COLLABORATED_WITH]-(b)
                        ON CREATE SET r.paper_count = 1
                        ON MATCH SET r.paper_count = r.paper_count + 1
                        """,
                        {"id_a": str(auth_a), "id_b": str(auth_b)}
                    )
    logger.info("Collaboration relationships derived.")

def print_summary() -> None:
    """Print a summary of what was seeded."""
    counts = run_query(
        "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC"
    )
    print("\n=== Real Data Seed Summary ===")
    for row in counts:
        print(f"  {row['label']:20s}: {row['count']:5d} nodes")
    
    rel_counts = run_query(
        "MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS count ORDER BY count DESC"
    )
    print("\n  Relationships:")
    for row in rel_counts:
        print(f"  {row['rel']:25s}: {row['count']:5d}")
    print()

def main():
    logger.info("=== Starting database seed (Real Data Only) ===")
    
    print("This will CLEAR your Neo4j database and re-seed it with real data.")
    confirm = input("Type 'yes' to continue: ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        return

    data = load_real_data()

    try:
        clear_database()
        create_constraints()
        create_vector_indexes()
        seed_authors(data.get("AUTHORS", []))
        seed_papers(data.get("PAPERS", []))
        seed_collaborations(data.get("PAPERS", []))
        print_summary()
        logger.info("=== Seed completed successfully ===")
    except Exception as e:
        logger.exception("Seed failed: %s", e)
        raise
    finally:
        close_driver()

if __name__ == "__main__":
    main()
