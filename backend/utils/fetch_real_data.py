import argparse
import json
import os
from semanticscholar import SemanticScholar

def fetch_papers(query, limit=20):
    sch = SemanticScholar()
    print(f"Searching Semantic Scholar for: '{query}'...")
    
    # Search for papers with specific fields
    results = sch.search_paper(
        query, 
        limit=limit, 
        fields=['title', 'abstract', 'authors', 'year', 'citationCount', 'externalIds', 'venue']
    )
    
    papers = []
    authors_master = {}
    institutions_master = {} 
    
    for i, item in enumerate(results):
        # Format matching your PAPERS structure in seed_data.py
        paper = {
            "id": f"real_p{i}",
            "title": item.title,
            "abstract": item.abstract if item.abstract else "No abstract available.",
            "year": item.year if item.year else 2024,
            "citations_count": item.citationCount if item.citationCount else 0,
            "doi": item.externalIds.get('DOI', f"no-doi-{i}"),
            "authors": [],
            "journal_name": item.venue if item.venue else "Scientific Publication",
        }
        
        # Process Authors
        if item.authors:
            for auth in item.authors:
                # The auth object is an Author instance, not a dict
                current_auth_name = getattr(auth, 'name', 'Unknown Author')
                auth_id = getattr(auth, 'authorId', None)
                if not auth_id:
                    auth_id = f"unknown_{current_auth_name.replace(' ', '_')}"
                
                paper["authors"].append(auth_id)
                
                if auth_id not in authors_master:
                    authors_master[auth_id] = {
                        "id": auth_id,
                        "name": current_auth_name,
                        "h_index": 0, 
                        "email": f"{current_auth_name.lower().replace(' ', '.')}@research.org"
                    }
        
        papers.append(paper)
        print(f"Added: {item.title[:60]}...", flush=True)

        # Save progress incrementally
        output_data = {
            "PAPERS": papers,
            "AUTHORS": list(authors_master.values())
        }
        output_path = "real_research_data.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=4)

    if papers:
        print(f"\n Success! Final data saved to {output_path}", flush=True)
    else:
        print("\n No papers were found or fetched.", flush=True)
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", type=str, default="Knowledge Graphs", help="Search keyword")
    parser.add_argument("--limit", type=int, default=20, help="Number of papers to fetch")
    args = parser.parse_args()
    
    fetch_papers(args.query, args.limit)
