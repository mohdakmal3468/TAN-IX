"""
tools/policy_tools.py
---------------------
Semantic Policy Vector Search tool for TAN-IX agents.
Exposes:
- search_policy(query, top_k) -> Retrieves the most relevant statutory policy clauses and SLAs.

Uses vector cosine similarity over the indexed policy database (data/policy_index.json).
"""

import os
import sys
import json
import re
import math
from typing import List, Dict, Any, Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

DATA_DIR = os.path.join(ROOT_DIR, "data")
INDEX_PATH = os.path.join(DATA_DIR, "policy_index.json")

_cached_index: Optional[Dict[str, Any]] = None


def _load_or_build_index() -> Dict[str, Any]:
    """Loads the policy vector index from data/policy_index.json or builds it if missing."""
    global _cached_index
    if _cached_index is not None:
        return _cached_index

    if not os.path.exists(INDEX_PATH):
        from scripts.index_policies import index_all_policies
        _cached_index = index_all_policies()
        return _cached_index

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        _cached_index = json.load(f)
    return _cached_index


def _compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot = 0.0
    norm_a_sq = 0.0
    norm_b_sq = 0.0

    for a, b in zip(vec_a, vec_b):
        dot += a * b
        norm_a_sq += a * a
        norm_b_sq += b * b

    if norm_a_sq <= 0 or norm_b_sq <= 0:
        return 0.0

    return dot / (math.sqrt(norm_a_sq) * math.sqrt(norm_b_sq))


def search_policy(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Performs semantic vector search over UP Leather Industrial policies and regulations.

    Searches across:
    - Delivery SLAs by district (Kanpur, Unnao, Agra, Noida)
    - Transit permits and e-Way bill regulations
    - Emergency freight and ODOP 15% subsidies
    - Financial delegation and approval limits
    - Carrier compliance and vehicle standards
    - Highway blockade and disaster handling SOPs

    Args:
        query: Natural language policy or compliance query (e.g. 'delivery SLA for Agra').
        top_k: Number of relevant policy clauses to retrieve (default: 3).

    Returns:
        List[Dict[str, Any]]: Top matching policy clauses with relevance scores and snippets.
    """
    index_data = _load_or_build_index()
    chunks = index_data.get("chunks", [])

    if not chunks:
        return [{"message": "No indexed policy documents found."}]

    q_lower = query.lower().strip()
    q_words = re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", q_lower)

    # Detect if query mentions a specific UP district cluster
    query_clusters = [c for c in ["Agra", "Kanpur", "Unnao", "Noida"] if c.lower() in q_lower]

    engine = index_data.get("engine", "local-dense-vector-fallback")
    scored_chunks = []

    if engine == "google-text-embedding-004":
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        resp = client.models.embed_content(model="text-embedding-004", contents=query)
        q_vec = resp.embedding.values if hasattr(resp, "embedding") else resp.embeddings[0].values
    else:
        # Use local vocabulary vectorizer
        from scripts.index_policies import compute_vector
        vocab = index_data.get("vocabulary", [])
        idf = index_data.get("idf_weights", {})
        q_vec = compute_vector(query, vocab, idf)

    for chk in chunks:
        doc_vec = chk.get("embedding", [])
        sim = _compute_cosine_similarity(q_vec, doc_vec)

        # Contextual boost for exact cluster match
        if query_clusters:
            for qc in query_clusters:
                if qc in chk.get("cluster_scope", []):
                    sim += 0.15
                if qc.lower() in chk.get("section_title", "").lower():
                    sim += 0.20

        # Keyword alignment boost for critical terms in section header
        for qw in q_words:
            if qw in chk.get("section_title", "").lower():
                sim += 0.10

        scored_chunks.append({
            "doc_id": chk.get("chunk_id"),
            "doc_name": chk.get("doc_name"),
            "title": chk.get("doc_title"),
            "section": chk.get("section_title"),
            "cluster_scope": chk.get("cluster_scope", []),
            "similarity_score": round(min(1.0, max(0.0, sim)), 3),
            "text": chk.get("text", "")
        })

    # Sort descending by similarity score
    scored_chunks.sort(key=lambda x: x["similarity_score"], reverse=True)
    top_results = scored_chunks[:top_k]

    # Format user-facing output
    formatted_results = []
    for r in top_results:
        # Build concise preview snippet
        lines = [line.strip() for line in r["text"].split("\n") if line.strip() and not line.startswith("#")]
        snippet = " ".join(lines[:3]) if lines else r["text"][:200]
        if len(snippet) > 280:
            snippet = snippet[:280] + "..."

        formatted_results.append({
            "doc_name": r["doc_name"],
            "title": r["title"],
            "section": r["section"],
            "similarity_score": r["similarity_score"],
            "cluster_scope": r["cluster_scope"],
            "snippet": snippet,
            "full_clause": r["text"]
        })

    return formatted_results


# ==============================================================================
# STANDALONE TEST RUNNER
# ==============================================================================

if __name__ == "__main__":
    test_query = "delivery SLA for Agra"
    print("=" * 75)
    print("POLICY VECTOR SEARCH TEST")
    print(f"Query: '{test_query}'")
    print("=" * 75)

    results = search_policy(test_query, top_k=2)

    for idx, match in enumerate(results, 1):
        print(f"\n[Match {idx}] {match['title']} -> {match['section']}")
        print(f"  Document File:    {match['doc_name']}")
        print(f"  Similarity Score: {match['similarity_score']}")
        print(f"  Cluster Scope:    {', '.join(match['cluster_scope'])}")
        print(f"  Snippet:          {match['snippet']}")
        print("-" * 75)
