"""
Test script for embedding files using the API.
"""

import requests
import json
from pathlib import Path

API_BASE = "http://localhost:8000"


def test_text_file_ingestion():
    """Test ingesting a text file."""
    test_dir = Path(__file__).parent

    # Test sample1.txt
    with open(test_dir / "sample1.txt", "rb") as f:
        response = requests.post(
            f"{API_BASE}/ingest/text/file",
            files={"file": ("sample1.txt", f, "text/plain")},
            data={"tags": "machine-learning,ai,deep-learning"},
        )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200


def test_multiple_text_files():
    """Test ingesting multiple text files."""
    test_dir = Path(__file__).parent

    files = ["sample1.txt", "sample2.txt", "sample3.txt"]
    tags = ["machine-learning,ai", "vector-database,embeddings", "nlp,transformers"]

    for file, tag in zip(files, tags):
        with open(test_dir / file, "rb") as f:
            response = requests.post(
                f"{API_BASE}/ingest/text/file",
                files={"file": (file, f, "text/plain")},
                data={"tags": tag},
            )
        print(f"\n{file}:")
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Chunks ingested: {data.get('chunks_ingested', 0)}")
            print(f"  Collection: {data.get('collection', '')}")
        else:
            print(f"  Error: {response.text}")


def test_text_search():
    """Test searching for text."""
    query = "What are vector databases used for?"

    response = requests.post(
        f"{API_BASE}/search/text", json={"query": query, "limit": 3}
    )

    print(f"\nSearch Query: {query}")
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"Found {len(data.get('results', []))} results:")
        for i, result in enumerate(data.get("results", []), 1):
            print(f"\n  Result {i}:")
            print(f"    Score: {result.get('score', 0):.4f}")
            print(f"    Text: {result.get('text', '')[:100]}...")
            print(f"    Source: {result.get('source_path', '')}")
    else:
        print(f"Error: {response.text}")


def test_health():
    """Test health endpoint."""
    response = requests.get(f"{API_BASE}/health")
    print(f"\nHealth Check:")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Embedding Service")
    print("=" * 60)

    # Test health first
    test_health()

    # Test ingestion
    print("\n" + "=" * 60)
    print("Testing File Ingestion")
    print("=" * 60)
    test_multiple_text_files()

    # Test search
    print("\n" + "=" * 60)
    print("Testing Search")
    print("=" * 60)
    test_text_search()

    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)
