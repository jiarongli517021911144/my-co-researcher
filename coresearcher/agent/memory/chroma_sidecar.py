from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

_COLLECTION_METADATA = {
    "hnsw:space": "cosine",
    "embedding_model": "onnx_minilm_l6_v2",
    "embedding_dim": 384,
}


def _sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, str | int | float | bool]:
    clean: dict[str, str | int | float | bool] = {}
    for key, value in (metadata or {}).items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
        else:
            clean[key] = json.dumps(value, ensure_ascii=False)
    return clean


def _client(db_dir: str):
    return chromadb.PersistentClient(path=db_dir, settings=Settings(anonymized_telemetry=False))


def _collection(client, name: str, *, create: bool):
    if create:
        return client.get_or_create_collection(name=name, metadata=_COLLECTION_METADATA)
    try:
        return client.get_collection(name=name)
    except Exception:
        return None


def _embedding_fn():
    return DefaultEmbeddingFunction()


def _read_payload() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else {}


def _to_result(raw: dict[str, Any]) -> list[dict[str, Any]]:
    documents = (raw.get("documents") or [[]])[0]
    metadatas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]
    results: list[dict[str, Any]] = []
    for index, document in enumerate(documents):
        distance = distances[index] if index < len(distances) else None
        metadata = metadatas[index] if index < len(metadatas) else {}
        score = max(0.0, 1.0 - float(distance)) if distance is not None else 0.0
        results.append({"text": document, "metadata": metadata or {}, "score": score, "distance": distance})
    return results


def _serialize_vector(vector: Any) -> list[float] | None:
    if vector is None:
        return None
    if hasattr(vector, "tolist"):
        return vector.tolist()
    if isinstance(vector, list):
        return vector
    return list(vector)


def _rows_from_records(raw: dict[str, Any], *, include_embeddings: bool) -> list[dict[str, Any]]:
    ids = raw.get("ids") or []
    documents = raw.get("documents") or []
    metadatas = raw.get("metadatas") or []
    embeddings = raw.get("embeddings")

    rows: list[dict[str, Any]] = []
    for index, doc_id in enumerate(ids):
        row: dict[str, Any] = {"id": doc_id}
        if index < len(documents):
            row["text"] = documents[index]
        if index < len(metadatas):
            row["metadata"] = metadatas[index] or {}
        if include_embeddings and embeddings is not None and index < len(embeddings):
            row["embedding"] = _serialize_vector(embeddings[index])
        rows.append(row)
    return rows


def main() -> int:
    if len(sys.argv) < 4:
        raise SystemExit("usage: chroma_sidecar.py <op> <db_dir> <collection>")
    op, db_dir, collection_name = sys.argv[1:4]
    Path(db_dir).mkdir(parents=True, exist_ok=True)
    client = _client(db_dir)
    payload = _read_payload()

    if op == "ping":
        print(json.dumps({"ok": True}))
        return 0

    if op == "count":
        collection = _collection(client, collection_name, create=False)
        print(json.dumps({"count": collection.count() if collection is not None else 0}))
        return 0

    if op == "meta":
        collection = _collection(client, collection_name, create=False)
        print(json.dumps(collection.metadata or {}, ensure_ascii=False) if collection is not None else "{}")
        return 0

    if op == "peek":
        collection = _collection(client, collection_name, create=False)
        if collection is None:
            print("[]")
            return 0
        limit = int(payload.get("limit") or 10)
        include_embeddings = bool(payload.get("include_embeddings"))
        raw = collection.peek(limit=limit)
        print(json.dumps(_rows_from_records(raw, include_embeddings=include_embeddings), ensure_ascii=False))
        return 0

    if op == "get":
        collection = _collection(client, collection_name, create=False)
        if collection is None:
            print("[]")
            return 0
        limit = int(payload.get("limit") or 20)
        offset = int(payload.get("offset") or 0)
        include_embeddings = bool(payload.get("include_embeddings"))
        include = ["documents", "metadatas"]
        if include_embeddings:
            include.append("embeddings")
        raw = collection.get(limit=limit, offset=offset, include=include)
        print(json.dumps(_rows_from_records(raw, include_embeddings=include_embeddings), ensure_ascii=False))
        return 0

    if op == "reset":
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass
        client.get_or_create_collection(name=collection_name, metadata=_COLLECTION_METADATA)
        print(json.dumps({"ok": True}))
        return 0

    if op == "add":
        collection = _collection(client, collection_name, create=True)
        embedding_fn = _embedding_fn()
        text = payload["text"]
        metadata = _sanitize_metadata(payload.get("metadata"))
        doc_id = payload.get("id") or uuid.uuid4().hex
        collection.add(
            ids=[doc_id],
            documents=[text],
            embeddings=embedding_fn([text]),
            metadatas=[metadata],
        )
        print(json.dumps({"id": doc_id}))
        return 0

    if op == "search":
        collection = _collection(client, collection_name, create=False)
        if collection is None:
            print("[]")
            return 0
        embedding_fn = _embedding_fn()
        query = payload["query"]
        limit = int(payload.get("limit") or 5)
        count = collection.count()
        if count <= 0:
            print("[]")
            return 0
        raw = collection.query(
            query_embeddings=embedding_fn([query]),
            n_results=min(limit, count),
            include=["documents", "metadatas", "distances"],
        )
        print(json.dumps(_to_result(raw), ensure_ascii=False))
        return 0

    raise SystemExit(f"unsupported op: {op}")


if __name__ == "__main__":
    raise SystemExit(main())
