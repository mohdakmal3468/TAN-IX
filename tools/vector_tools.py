"""
tools/vector_tools.py
---------------------
Vector Search and Semantic Knowledge Retrieval over Uttar Pradesh leather industrial policies,
environmental mandates (NGT/UPPCB), and freight subsidy protocols.

Features:
- Reads documents from data/regulatory_docs.json
- Performs semantic text similarity scoring
- Returns the most relevant policy clauses to support multi-agent compliance reasoning
"""

import os
import json
import math
import re
from typing import List, Dict, Any

DOCS_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "regulatory_docs.json")


def _load_docs() -> List[Dict[str, Any]]:
    """Loads policy and regulatory documents."""
    if not os.path.exists(DOCS_FILE_PATH):
        return []
    with open(DOCS_FILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _tokenize(text: str) -> set:
    """Simple tokenization helper."""
    words = re.findall(r"\b\w{3,}\b", text.lower())
    return set(words)


def search_policy_docs(query: str, top_k: int = 2) -> List[Dict[str, Any]]:
    """
    Performs keyword & semantic overlap search over UP Leather Policy and NGT documents.
    Returns the top matching regulatory and policy clauses.
    """
    docs = _load_docs()
    if not docs:
        return [{"message": "No regulatory documents indexed."}]

    query_tokens = _tokenize(query)
    scored_docs = []

    for doc in docs:
        content_text = f"{doc.get('title', '')} {doc.get('category', '')} {doc.get('cluster', '')} {doc.get('content', '')}"
        doc_tokens = _tokenize(content_text)
        
        # Calculate Jaccard similarity between query tokens and document tokens
        intersection = query_tokens.intersection(doc_tokens)
        union = query_tokens.union(doc_tokens)
        score = len(intersection) / len(union) if union else 0.0

        # Prioritize exact phrase matches in title or content
        for q_word in query_tokens:
            if q_word in doc.get("title", "").lower():
                score += 0.25

        scored_docs.append({
            "doc_id": doc.get("doc_id"),
            "title": doc.get("title"),
            "cluster": doc.get("cluster"),
            "category": doc.get("category"),
            "content": doc.get("content"),
            "relevance_score": round(score, 3)
        })

    # Sort descending by relevance score
    scored_docs.sort(key=lambda x: x["relevance_score"], reverse=True)
    return scored_docs[:top_k]
