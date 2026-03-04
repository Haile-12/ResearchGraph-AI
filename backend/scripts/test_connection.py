from neo4j import GraphDatabase

URI = "neo4j://127.0.0.1:7687"
database="researchgraph"
AUTH = ("neo4j", "*************") # Replace with your password

def connect_to_graph():
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        try:
            driver.verify_connectivity()
            print("Connected to Graph AI instance!")
            
            # Running a query on'researchgraph' database
            records, _, _ = driver.execute_query(
                "MATCH (n) RETURN count(n) AS node_count",
                database_=database
            )
            print(f"Nodes in researchgraph: {records[0]['node_count']}")

        except Exception as e:
            print(f"Connection failed: {e}")

if __name__ == "__main__":
    connect_to_graph()
