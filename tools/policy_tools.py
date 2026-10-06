"""
tools/policy_tools.py   (USE ONLY IF YOUR PROJECT DOES NOT ALREADY HAVE ONE)
Thin wrapper over tools/vector_tools.py so the orchestrator can call search_policy().
"""
from tools.vector_tools import search_policy_docs


def search_policy(query: str, top_k: int = 3) -> list:
    """Find the policy clauses most relevant to a plain-English question.

    Args:
        query: e.g. "delivery SLA for Agra".
        top_k: how many clauses to return.

    Returns:
        A list of dicts: doc_name, title, content, score.
    """
    results = []
    for m in search_policy_docs(query, top_k=top_k) or []:
        results.append({
            "doc_name": m.get("doc_name") or m.get("category") or m.get("title", "policy"),
            "title": m.get("title", ""),
            "content": m.get("content") or m.get("text", ""),
            "score": m.get("relevance_score"),
        })
    return results