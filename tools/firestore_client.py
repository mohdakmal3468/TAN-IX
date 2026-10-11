"""
tools/firestore_client.py
-------------------------
Reusable utility module for Google Cloud Firestore operations in AgentHide.
Provides type-safe helper functions for:
- get_document
- set_document
- list_documents
- batch_write_documents
- get_collection_count
"""

import os
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Project ID resolution with priority to GOOGLE_CLOUD_PROJECT
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCP_PROJECT_ID", "agenthide-demo"))
DATABASE_NAME = os.getenv("FIRESTORE_DATABASE", "(default)")

USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "true").lower() in ("true", "1", "yes")

_client_instance = None  # None = not tried, False = failed/mock, Client = active


def get_firestore_client():
    """
    Initializes or returns a singleton Google Cloud Firestore client.
    Returns None if in mock mode, google-cloud-firestore is unavailable, or credentials fail.
    """
    global _client_instance
    if _client_instance is False:
        return None
    if _client_instance is not None:
        return _client_instance

    if USE_MOCK_DATA:
        _client_instance = False
        return None

    try:
        from google.cloud import firestore
        _client_instance = firestore.Client(project=PROJECT_ID, database=DATABASE_NAME)
        return _client_instance
    except Exception as e:
        _client_instance = False
        return None


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
MOCK_DIR = os.path.join(DATA_DIR, "firestore_mock")


def _get_mock_collection_path(collection: str) -> str:
    """Returns the local mock JSON path for a collection."""
    os.makedirs(MOCK_DIR, exist_ok=True)
    return os.path.join(MOCK_DIR, f"{collection}.json")


def _match_doc_id(item: Dict[str, Any], doc_id: str) -> bool:
    """Checks if a dictionary item matches the requested document ID."""
    candidate_keys = ["_id", "id", "run_id", "request_id", "plan_id", "inventory_id", "event_id", "lane_id", "shipment_id", "route_id", "carrier_id"]
    for k in candidate_keys:
        if str(item.get(k, "")) == str(doc_id):
            return True
    return False


def get_document(collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a single document from a Firestore collection by ID.
    Falls back to data/firestore_mock/<collection>.json when client is unavailable.
    """
    client = get_firestore_client()
    if client is not None:
        try:
            doc_ref = client.collection(collection).document(doc_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                data["_id"] = doc.id
                return data
        except Exception as e:
            print(f"[Firestore Error] get_document failed for {collection}/{doc_id}: {e}")

    # Fallback to local mock data
    mock_file = _get_mock_collection_path(collection)
    if os.path.exists(mock_file) and os.path.getsize(mock_file) > 0:
        try:
            with open(mock_file, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and _match_doc_id(item, doc_id):
                            return item
                elif isinstance(content, dict):
                    if doc_id in content:
                        res = content[doc_id]
                        if isinstance(res, dict) and "_id" not in res:
                            res["_id"] = doc_id
                        return res
        except Exception as e:
            print(f"[Firestore Mock Error] Reading {mock_file}: {e}")

    return None


def set_document(collection: str, doc_id: str, data: Dict[str, Any], merge: bool = True) -> bool:
    """
    Writes or merges a single document into a Firestore collection.
    Automatically saves to data/firestore_mock/<collection>.json as a persistent fallback.
    """
    client = get_firestore_client()
    firestore_success = False

    if client is not None:
        try:
            doc_ref = client.collection(collection).document(doc_id)
            doc_ref.set(data, merge=merge)
            firestore_success = True
        except Exception as e:
            print(f"[Firestore Error] set_document failed for {collection}/{doc_id}: {e}")

    # Synchronize to local mock store
    try:
        mock_file = _get_mock_collection_path(collection)
        items = []
        if os.path.exists(mock_file) and os.path.getsize(mock_file) > 0:
            with open(mock_file, "r", encoding="utf-8") as f:
                try:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        items = loaded
                    elif isinstance(loaded, dict):
                        items = list(loaded.values())
                except json.JSONDecodeError:
                    items = []

        # Update or append
        doc_entry = dict(data)
        doc_entry["_id"] = doc_id
        if "id" not in doc_entry and not any(k in doc_entry for k in ["run_id", "request_id", "inventory_id"]):
            doc_entry["id"] = doc_id

        found_index = -1
        for idx, itm in enumerate(items):
            if isinstance(itm, dict) and _match_doc_id(itm, doc_id):
                found_index = idx
                break

        if found_index >= 0:
            if merge:
                items[found_index].update(doc_entry)
            else:
                items[found_index] = doc_entry
        else:
            items.insert(0, doc_entry)

        with open(mock_file, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)

        return True
    except Exception as e:
        print(f"[Firestore Mock Error] Writing {collection}/{doc_id}: {e}")
        return firestore_success


def list_documents(collection: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetches up to `limit` documents from a collection.
    Falls back to data/firestore_mock/<collection>.json when client is unavailable.
    """
    client = get_firestore_client()
    if client is not None:
        try:
            docs = client.collection(collection).limit(limit).stream()
            results = []
            for doc in docs:
                item = doc.to_dict()
                item["_id"] = doc.id
                results.append(item)
            if results:
                return results
        except Exception as e:
            print(f"[Firestore Error] list_documents failed for {collection}: {e}")

    # Fallback to local mock data
    mock_file = _get_mock_collection_path(collection)
    if os.path.exists(mock_file) and os.path.getsize(mock_file) > 0:
        try:
            with open(mock_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    return loaded[:limit]
                elif isinstance(loaded, dict):
                    return list(loaded.values())[:limit]
        except Exception as e:
            print(f"[Firestore Mock Error] Listing {collection}: {e}")

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
