"""
tools/firestore_client.py
-------------------------
Reusable utility module for Google Cloud Firestore operations in TAN-IX.
Provides type-safe helper functions for:
- get_document
- set_document
- list_documents
- batch_write_documents
- get_collection_count
"""

import os
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Project ID resolution with priority to GOOGLE_CLOUD_PROJECT
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCP_PROJECT_ID", "tan-ix-demo"))
DATABASE_NAME = os.getenv("FIRESTORE_DATABASE", "(default)")

_client_instance = None


def get_firestore_client():
    """
    Initializes or returns a singleton Google Cloud Firestore client.
    Returns None if google-cloud-firestore is unavailable or credentials fail.
    """
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    try:
        from google.cloud import firestore
        _client_instance = firestore.Client(project=PROJECT_ID, database=DATABASE_NAME)
        return _client_instance
    except Exception as e:
        # Note the exception without crashing; callers can handle fallback
        return None


def get_document(collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a single document from a Firestore collection by ID.
    Returns dictionary of document fields, or None if not found.
    """
    client = get_firestore_client()
    if client is None:
        return None

    try:
        doc_ref = client.collection(collection).document(doc_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            data["_id"] = doc.id
            return data
        return None
    except Exception as e:
        print(f"[Firestore Error] get_document failed for {collection}/{doc_id}: {e}")
        return None


def set_document(collection: str, doc_id: str, data: Dict[str, Any], merge: bool = True) -> bool:
    """
    Writes or merges a single document into a Firestore collection.
    """
    client = get_firestore_client()
    if client is None:
        return False

    try:
        doc_ref = client.collection(collection).document(doc_id)
        doc_ref.set(data, merge=merge)
        return True
    except Exception as e:
        print(f"[Firestore Error] set_document failed for {collection}/{doc_id}: {e}")
        return False


def list_documents(collection: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetches up to `limit` documents from a collection.
    """
    client = get_firestore_client()
    if client is None:
        return []

    try:
        docs = client.collection(collection).limit(limit).stream()
        results = []
        for doc in docs:
            item = doc.to_dict()
            item["_id"] = doc.id
            results.append(item)
        return results
    except Exception as e:
        print(f"[Firestore Error] list_documents failed for {collection}: {e}")
        return []


def batch_write_documents(collection: str, documents: List[Dict[str, Any]], id_key: str = "id") -> int:
    """
    Performs chunked batch writes (up to 500 documents per batch, conforming to Firestore limits).
    Returns total count of successfully committed documents.
    """
    client = get_firestore_client()
    if client is None or not documents:
        return 0

    total_committed = 0
    batch_size = 450  # Conservative margin below 500 limit

    try:
        for i in range(0, len(documents), batch_size):
            chunk = documents[i:i + batch_size]
            batch = client.batch()

            for doc_data in chunk:
                # Determine document ID
                doc_id = str(doc_data.get(id_key) or doc_data.get("_id") or f"doc_{total_committed + 1}")
                doc_ref = client.collection(collection).document(doc_id)
                batch.set(doc_ref, doc_data, merge=True)

            batch.commit()
            total_committed += len(chunk)

        return total_committed
    except Exception as e:
        print(f"[Firestore Error] batch_write_documents failed for {collection}: {e}")
        return total_committed


def get_collection_count(collection: str) -> int:
    """
    Counts total documents in a collection using Firestore aggregation query.
    """
    client = get_firestore_client()
    if client is None:
        return 0

    try:
        from google.cloud.firestore_v1.base_aggregation import count
        col_ref = client.collection(collection)
        aggregate_query = col_ref.count()
        results = aggregate_query.get()
        return int(results[0][0].value)
    except Exception:
        # Fallback to stream count if aggregation query not supported
        try:
            return sum(1 for _ in client.collection(collection).stream())
        except Exception:
            return 0
