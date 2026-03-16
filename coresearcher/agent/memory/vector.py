from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

_CHROMA_IMPORT_ERROR: Exception | None = None
if sys.version_info < (3, 14):
    try:  # pragma: no cover - exercised indirectly in runtime
        import chromadb
        from chromadb.config import Settings
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    except Exception as exc:  # pragma: no cover
        chromadb = None
        Settings = None
        DefaultEmbeddingFunction = None
        _CHROMA_IMPORT_ERROR = exc
else:  # pragma: no cover
    chromadb = None
    Settings = None
    DefaultEmbeddingFunction = None
    _CHROMA_IMPORT_ERROR = RuntimeError("chromadb direct import disabled on Python 3.14+")

_COLLECTION_NAME = "daily_memories"
_COLLECTION_METADATA = {
    "hnsw:space": "cosine",
    "embedding_model": "onnx_minilm_l6_v2",
    "embedding_dim": 384,
}
_SIDECAR_ENV = "CORESEARCHER_CHROMA_PYTHON"


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


class _DirectChromaBackend:
    def __init__(self, chroma_dir: Path, collection_name: str) -> None:
        self.client = chromadb.PersistentClient(
            path=str(chroma_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata=_COLLECTION_METADATA,
        )
        self.embedding_fn = DefaultEmbeddingFunction()

    def add(self, text: str, metadata: dict[str, Any] | None = None) -> str:
        doc_id = uuid.uuid4().hex
        self.collection.add(
            ids=[doc_id],
            documents=[text],
            embeddings=self.embedding_fn([text]),
            metadatas=[_sanitize_metadata(metadata)],
        )
        return doc_id

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        count = self.collection.count()
        if count <= 0:
            return []
        raw = self.collection.query(
            query_embeddings=self.embedding_fn([query]),
            n_results=min(limit, count),
            include=["documents", "metadatas", "distances"],
        )
        return _format_query_result(raw)

    def count(self) -> int:
        return self.collection.count()

    def metadata(self) -> dict[str, Any]:
        return self.collection.metadata or {}

    def reset(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata=_COLLECTION_METADATA,
        )


class _SidecarChromaBackend:
    def __init__(self, chroma_dir: Path, collection_name: str) -> None:
        self.python = self._find_python()
        self.script = Path(__file__).with_name("chroma_sidecar.py")
        self.chroma_dir = chroma_dir
        self.collection_name = collection_name
        self._run("ping")

    def add(self, text: str, metadata: dict[str, Any] | None = None) -> str:
        result = self._run("add", {"text": text, "metadata": metadata})
        return str(result.get("id", ""))

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        result = self._run("search", {"query": query, "limit": limit})
        return result if isinstance(result, list) else []

    def count(self) -> int:
        result = self._run("count")
        return int(result.get("count", 0))

    def metadata(self) -> dict[str, Any]:
        result = self._run("meta")
        return result if isinstance(result, dict) else {}

    def reset(self) -> None:
        self._run("reset")

    def _find_python(self) -> str:
        if os.environ.get(_SIDECAR_ENV):
            return os.environ[_SIDECAR_ENV]
        for name in ["python3.12", "python3.13"]:
            path = shutil.which(name)
            if path:
                return path
        raise RuntimeError(
            "ChromaDB is unavailable in the current interpreter and no python3.12/python3.13 sidecar was found."
        )

    def _run(self, op: str, payload: dict[str, Any] | None = None) -> Any:
        cmd = [self.python, str(self.script), op, str(self.chroma_dir), self.collection_name]
        completed = subprocess.run(
            cmd,
            input=json.dumps(payload or {}, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Chroma sidecar failed ({completed.returncode}): {completed.stderr.strip() or completed.stdout.strip()}"
            )
        output = completed.stdout.strip()
        return json.loads(output) if output else {}


class VectorIndex:
    def __init__(self, chroma_dir: str | Path, collection_name: str = _COLLECTION_NAME) -> None:
        self.chroma_dir = Path(chroma_dir).expanduser()
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.legacy_path = self.chroma_dir.parent / ".vector_index.jsonl"
        self.legacy_backup_path = self.chroma_dir.parent / ".vector_index.jsonl.legacy"
        self.collection_name = collection_name

        if chromadb is not None and sys.version_info < (3, 14):
            self._backend = _DirectChromaBackend(self.chroma_dir, collection_name)
            self.backend_name = "direct"
        else:
            logger.info("Direct chromadb import unavailable in this interpreter: {}", _CHROMA_IMPORT_ERROR)
            self._backend = _SidecarChromaBackend(self.chroma_dir, collection_name)
            self.backend_name = "sidecar"

        self._ensure_collection_compatible()
        self._maybe_migrate_legacy_index()
        logger.info(
            "Vector index ready | backend={} | chroma_dir={} | collection={} | count={}",
            self.backend_name,
            self.chroma_dir,
            self.collection_name,
            self.count(),
        )

    def add(self, text: str, metadata: dict[str, Any] | None = None) -> str:
        return self._backend.add(text, metadata)

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return self._backend.search(query, limit=limit)

    def count(self) -> int:
        return self._backend.count()

    def _ensure_collection_compatible(self) -> None:
        metadata = self._backend.metadata()
        if metadata.get("embedding_model") == _COLLECTION_METADATA["embedding_model"]:
            return
        if self.count() == 0:
            self._backend.reset()
            return
        source = self.legacy_backup_path if self.legacy_backup_path.exists() else None
        if source is None:
            logger.warning(
                "Existing Chroma collection is incompatible with current embedding model, but no legacy backup was found. Keeping existing data."
            )
            return
        logger.info(
            "Rebuilding incompatible Chroma collection from legacy backup | source={}",
            source,
        )
        self._backend.reset()
        self._migrate_from_file(source, rename_source=False)

    def _maybe_migrate_legacy_index(self) -> None:
        if not self.legacy_path.exists():
            return
        if self.count() > 0:
            logger.info(
                "Skipping legacy vector migration | chroma already has data | legacy_path={}",
                self.legacy_path,
            )
            return
        self._migrate_from_file(self.legacy_path, rename_source=True)

    def _migrate_from_file(self, source: Path, *, rename_source: bool) -> None:
        migrated = 0
        for line in source.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            self.add(record.get("text", ""), record.get("metadata", {}))
            migrated += 1
        if migrated <= 0:
            return
        if rename_source:
            backup = self.legacy_backup_path
            source.rename(backup)
        else:
            backup = source
        logger.info(
            "Migrated legacy vector index to ChromaDB | migrated={} | backup={}",
            migrated,
            backup,
        )


def _format_query_result(raw: dict[str, Any]) -> list[dict[str, Any]]:
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
