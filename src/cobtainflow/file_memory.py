"""
File-based memory storage backend for CrewAI Memory.

Architecture:
  FileMemory (inherits CrewAI Memory)
    └─ _storage: FileStorageBackend (StorageBackend protocol)
                    ├─ save()     → write md files + ChromaDB vector index
                    ├─ search()   → ChromaDB vector search + keyword filter
                    └─ ...other StorageBackend methods...

ChromaDB is used ONLY as a vector index (stores vectors + metadata).
md files are the source of truth for full content.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Literal, Optional, Union

import chromadb
from crewai.memory.unified_memory import Memory
from crewai.memory.storage.backend import StorageBackend, MemoryRecord, ScopeInfo
from openai import OpenAI
from rank_bm25 import BM25Okapi


# ------------------------------------------------------------------
# Embedding function (moved from old memory_factory.py)
# ------------------------------------------------------------------

EMBEDDING_DIMENSIONS = 1024


def _embedding_callable(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    client = OpenAI(
        api_key=os.getenv("EMBEDDING_API_KEY"),
        base_url=os.getenv("EMBEDDING_BASE_URL"),
    )
    all_embeddings: List[List[float]] = []
    for i in range(0, len(texts), 10):
        batch = texts[i : i + 10]
        completion = client.embeddings.create(
            model="text-embedding-v4",
            input=batch,
            dimensions=EMBEDDING_DIMENSIONS,
            encoding_format="float",
        )
        all_embeddings.extend([item.embedding for item in completion.data])
    # Sanitize: remove surrogate characters that cause encode errors
    sanitized: List[List[float]] = []
    for emb in all_embeddings:
        try:
            str(emb).encode("utf-8")
            sanitized.append(emb)
        except UnicodeEncodeError:
            sanitized.append([v for v in emb if not (0xD800 <= v <= 0xDFFF)])
    return sanitized


class EmbeddingError(Exception):
    """Raised when embedding computation fails."""


# ------------------------------------------------------------------
# ChromaDB embedding function for CrewAI StorageBackend
# ------------------------------------------------------------------


class _ChromaEmbeddingFunction:
    """Compatible with ChromaDB's EmbeddingFunction protocol."""

    def __call__(self, input: List[str]) -> List[List[float]]:
        try:
            embeddings = _embedding_callable(input)
        except Exception as e:
            raise EmbeddingError(f"Embedding failed: {e}") from e
        if embeddings and all(abs(v) < 1e-9 for emb in embeddings for v in emb):
            raise EmbeddingError("Embedding returned all-zero vectors — check API key and endpoint.")
        return embeddings

    def embed_query(self, input: str) -> List[float]:
        try:
            embeddings = _embedding_callable([input])
        except Exception as e:
            raise EmbeddingError(f"Query embedding failed: {e}") from e
        if not embeddings or all(abs(v) < 1e-9 for v in embeddings[0]):
            raise EmbeddingError("Query embedding returned zero vectors.")
        return embeddings[0]

    def name(self) -> str:
        return "custom-embedding-v4"


# ------------------------------------------------------------------
# FileStorageBackend — CrewAI StorageBackend protocol implementation
# ------------------------------------------------------------------


class FileStorageBackend(StorageBackend):
    """
    File-backed storage: md files as source of truth + ChromaDB vector index.

    Scope convention:
      /agent/searcher/{session_id}/round-{n}
      /agent/organizer/{session_id}/round-{n}
      /global/searcher
      /global/organizer
    """

    COLLECTION_NAME = "agent_memories"

    def __init__(
        self,
        storage_dir: str | None = None,
        *,
        round_counter_path: str | None = None,
    ):
        if storage_dir is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            storage_dir = str(project_root / "memory")

        self._storage_dir = Path(storage_dir)
        self._index_dir = self._storage_dir / "index_chroma"
        self._index_dir.mkdir(parents=True, exist_ok=True)

        # Round counters: scope → current round number
        self._round_counters: dict[str, int] = {}
        self._round_counter_path = round_counter_path or str(
            self._storage_dir / "round_counters.json"
        )
        self._load_round_counters()

        # ChromaDB
        self._chroma = chromadb.PersistentClient(path=str(self._index_dir))
        self._embedding_fn = _ChromaEmbeddingFunction()

        try:
            self._collection = self._chroma.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "Agent memory: md + ChromaDB vector index"},
                embedding_function=self._embedding_fn,
            )
        except Exception:
            # Corrupted index — wipe and recreate
            def _onerror(func, path, exc_info):
                import stat
                os.chmod(path, stat.S_IWRITE)
                try:
                    os.unlink(path)
                except OSError:
                    pass

            shutil.rmtree(self._index_dir, onerror=_onerror)
            self._index_dir.mkdir(parents=True, exist_ok=True)
            self._chroma = chromadb.PersistentClient(path=str(self._index_dir))
            self._embedding_fn = _ChromaEmbeddingFunction()
            self._collection = self._chroma.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "Agent memory: md + ChromaDB vector index"},
                embedding_function=self._embedding_fn,
            )

    # ------------------------------------------------------------------
    # Round counter helpers
    # ------------------------------------------------------------------

    def _load_round_counters(self) -> None:
        if Path(self._round_counter_path).exists():
            with open(self._round_counter_path, "r", encoding="utf-8") as f:
                self._round_counters = json.load(f)

    def _save_round_counters(self) -> None:
        with open(self._round_counter_path, "w", encoding="utf-8") as f:
            json.dump(self._round_counters, f, ensure_ascii=False, indent=2)

    def _next_round_number(self, scope: str) -> int:
        n = self._round_counters.get(scope, 0) + 1
        self._round_counters[scope] = n
        self._save_round_counters()
        return n

    # ------------------------------------------------------------------
    # md file helpers
    # ------------------------------------------------------------------

    def _scope_to_dir(self, scope: str) -> Path:
        safe = scope.strip("/").replace("/", os.sep)
        return self._storage_dir / safe

    def _write_md(
        self,
        scope: str,
        content: str,
        metadata: dict[str, Any],
        filename: str,
    ) -> Path:
        dir_path = self._scope_to_dir(scope)
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / filename

        frontmatter: dict[str, Any] = {
            "scope": scope,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **metadata,
        }
        fm_text = json.dumps(frontmatter, ensure_ascii=False, indent=2)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write(fm_text)
            f.write("\n---\n")
            f.write(content.strip())
            f.write("\n")

        return file_path

    def _read_md(self, file_path: Path) -> tuple[dict[str, Any], str]:
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()

        if not raw.startswith("---"):
            return {}, raw

        end = raw.index("---", 3)
        fm_text = raw[3:end].strip()
        body = raw[end + 3 :].strip()

        try:
            metadata = json.loads(fm_text)
        except json.JSONDecodeError:
            metadata = {}

        return metadata, body

    def _glob_md(self, scope: str) -> List[Path]:
        dir_path = self._scope_to_dir(scope)
        if not dir_path.exists():
            return []
        return sorted(dir_path.glob("*.md"), key=lambda p: p.stat().st_mtime)

    def _memory_id_to_path(self, memory_id: str) -> Path | None:
        """Convert a memory id (e.g. 'global/searcher/sess123') to its md file path."""
        scope, _, rest = memory_id.partition("/")
        scope_prefix = "/" + scope
        rest_of_path = rest.rsplit("/", 1)[0] if "/" in rest else ""
        full_scope = scope_prefix + "/" + rest_of_path if rest_of_path else scope_prefix
        dir_path = self._scope_to_dir(full_scope)
        filename = (rest.rsplit("/", 1)[-1] or "") + ".md"
        file_path = dir_path / filename
        return file_path if file_path.exists() else None

    def _parse_md_filename(self, filename: str) -> str:
        """Extract memory id from md filename like 'sess123-round-1.md' → 'sess123-round-1'"""
        return filename.removesuffix(".md")

    # ------------------------------------------------------------------
    # StorageBackend: save
    # ------------------------------------------------------------------

    def save(self, records: List[MemoryRecord]) -> None:
        """Write records to md files and register vectors in ChromaDB."""
        for record in records:
            scope = record.scope or "/"
            is_global = scope.startswith("/global/")
            round_num = self._next_round_number(scope) if not is_global else 0

            # Parse session_id from record.metadata or generate
            session_id = (
                record.metadata.get("session_id", "")
                if record.metadata
                else ""
            )
            if not session_id:
                session_id = scope.split("/")[-1]

            # Filename: {session_id}-round-{n} for /agent/*, {session_id}.md for /global/*
            if is_global:
                filename = f"{session_id}.md"
                memory_id = f"{scope}/{session_id}"
            else:
                filename = f"{session_id}-round-{round_num}.md"
                memory_id = f"{scope}/{session_id}-round-{round_num}"

            metadata_for_file = {
                "categories": list(record.categories) if record.categories else [],
                "importance": record.importance,
                "source": record.source or "",
                "memory_id": memory_id,
            }

            # Write md file
            self._write_md(scope, record.content, metadata_for_file, filename)

            # Register in ChromaDB (embedding happens via the embedding_function)
            try:
                self._collection.add(
                    ids=[memory_id],
                    documents=[record.content],
                    metadatas=[{
                        "scope": scope,
                        "source": record.source or "",
                        "file_path": str(self._scope_to_dir(scope) / filename),
                        "memory_id": memory_id,
                    }],
                )
            except EmbeddingError:
                raise
            except Exception as e:
                raise EmbeddingError(f"Failed to add to ChromaDB: {e}") from e

    # ------------------------------------------------------------------
    # StorageBackend: search (hybrid BM25 + vector RRF)
    # ------------------------------------------------------------------

    def search(
        self,
        query_embedding: List[float],
        scope_prefix: str | None = None,
        categories: List[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> List[tuple[MemoryRecord, float]]:
        """
        Hybrid search: ChromaDB vector + BM25, fused with RRF (k=60).

        categories[0] is treated as raw query text for BM25 (set by HybridMemory.recall()).
        """
        RRF_K = 60

        # BM25 query: categories[0] contains raw query from HybridMemory
        bm25_query = categories[0] if categories else ""

        # ── Vector retrieval path ────────────────────────────────────────
        vector_candidates: dict[str, tuple[int, float]] = {}  # memory_id → (rank_1based, score)

        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(limit * 4, 20),
                include=["metadatas", "documents", "distances"],
            )
            chroma_ok = bool(results and results.get("ids") and results["ids"][0])
        except Exception:
            chroma_ok = False

        if chroma_ok:
            for rank, memory_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][rank] if rank < len(results["metadatas"][0]) else {}
                if scope_prefix and not meta.get("scope", "").startswith(scope_prefix):
                    continue
                file_path_str = meta.get("file_path", "")
                if not file_path_str or not Path(file_path_str).exists():
                    continue
                distance = results.get("distances", [[]])[0][rank] if rank < len(results.get("distances", [[]])[0]) else 0.0
                vector_score = max(0.0, 1.0 - distance / 2.0)
                vector_candidates[memory_id] = (rank + 1, vector_score)

        # ── BM25 retrieval path ──────────────────────────────────────────
        bm25_scores: dict[str, float] = {}
        if bm25_query:
            for memory_id, bm25_score in self._bm25_search(bm25_query, scope_prefix, limit * 4):
                bm25_scores[memory_id] = bm25_score

        # ── RRF fusion ───────────────────────────────────────────────────
        all_ids = set(vector_candidates) | set(bm25_scores)
        fused: List[tuple[str, float]] = []

        for memory_id in all_ids:
            v_rank = vector_candidates.get(memory_id, (0, 0.0))[0]
            bm_score = bm25_scores.get(memory_id, 0.0)

            if v_rank == 0 and bm_score == 0.0:
                continue

            if not vector_candidates or v_rank == 0:
                # No vector results → pure BM25 (normalized to [0,1])
                max_bm = max(bm25_scores.values()) if bm25_scores else 1.0
                rrf_score = max(0.0, min(1.0, bm_score / max_bm)) if max_bm > 0 else 0.0
            elif not bm25_scores:
                # No BM25 results → pure vector RRF
                rrf_score = 1.0 / (RRF_K + v_rank)
            else:
                # Both paths: vector RRF + BM25 normalized score
                max_bm = max(bm25_scores.values())
                norm_bm = bm_score / max_bm if max_bm > 0 else 0.0
                rrf_score = (1.0 / (RRF_K + v_rank)) + norm_bm

            fused.append((memory_id, rrf_score))

        fused.sort(key=lambda x: x[1], reverse=True)
        fused = fused[:limit]

        # ── Build MemoryRecord results ───────────────────────────────────
        records: List[tuple[MemoryRecord, float]] = []
        for memory_id, rrf_score in fused:
            if rrf_score < min_score:
                continue
            file_path = self._memory_id_to_path(memory_id)
            if not file_path or not file_path.exists():
                continue
            fm_meta, body = self._read_md(file_path)
            record = MemoryRecord(
                id=memory_id, content=body,
                scope=fm_meta.get("scope", "/"),
                categories=list(fm_meta.get("categories", [])),
                metadata={"source": fm_meta.get("source", "")},
                importance=fm_meta.get("importance", 0.5),
                source=fm_meta.get("source"),
            )
            records.append((record, rrf_score))

        return records

    def _build_bm25_index(self, scope_prefix: str | None = None):
        """Build BM25 index over md files in scope. Returns (bm25, id_to_path)."""
        scope = scope_prefix or "/"
        files = self._glob_md(scope)
        corpus = []
        id_to_path = []  # index → (memory_id, file_path)

        for f in sorted(files, key=lambda p: p.stat().st_mtime):
            fm_meta, body = self._read_md(f)
            memory_id = fm_meta.get("memory_id", str(f))
            corpus.append(body.lower())
            id_to_path.append((memory_id, f))

        if not corpus:
            return None, {}

        tokenized = [doc.split() for doc in corpus]
        bm25 = BM25Okapi(tokenized)
        return bm25, id_to_path

    def _bm25_search(
        self,
        query: str,
        scope_prefix: str | None = None,
        limit: int = 20,
    ) -> List[tuple[str, float]]:
        """BM25 retrieval path — returns (memory_id, bm25_score) sorted descending."""
        bm25, id_to_path = self._build_bm25_index(scope_prefix)
        if bm25 is None or not id_to_path:
            return []

        query_tokens = query.lower().split()
        scores = bm25.get_scores(query_tokens)

        scored = sorted(
            [(scores[i], id_to_path[i][0]) for i in range(len(scores)) if scores[i] > 0],
            key=lambda x: x[0],
            reverse=True,
        )
        return [(mid, score) for score, mid in scored[:limit]]

    # ------------------------------------------------------------------
    # StorageBackend: other methods (straightforward)
    # ------------------------------------------------------------------

    def delete(
        self,
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        record_ids: list[str] | None = None,
        older_than: datetime | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> int:
        deleted = 0
        scope = scope_prefix or "/"
        for f in self._glob_md(scope):
            fm_meta, _ = self._read_md(f)
            memory_id = fm_meta.get("memory_id", "")
            if record_ids and memory_id not in record_ids:
                continue
            if older_than:
                ts_str = fm_meta.get("timestamp", "")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if ts >= older_than:
                            continue
                    except ValueError:
                        pass
            f.unlink(missing_ok=True)
            try:
                self._collection.delete(ids=[memory_id])
            except Exception:
                pass
            deleted += 1
        return deleted

    def update(self, record: MemoryRecord) -> None:
        """Update: overwrite the md file and re-index in ChromaDB."""
        self.save([record])

    def get_record(self, record_id: str) -> MemoryRecord | None:
        file_path = self._memory_id_to_path(record_id)
        if not file_path:
            return None
        fm_meta, body = self._read_md(file_path)
        return MemoryRecord(
            id=record_id,
            content=body,
            scope=fm_meta.get("scope", "/"),
            categories=list(fm_meta.get("categories", [])),
            metadata={"source": fm_meta.get("source", "")},
            importance=fm_meta.get("importance", 0.5),
            source=fm_meta.get("source"),
        )

    def list_records(
        self,
        scope_prefix: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        scope = scope_prefix or "/"
        files = self._glob_md(scope)
        records: list[MemoryRecord] = []

        for f in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True):
            fm_meta, body = self._read_md(f)
            memory_id = fm_meta.get("memory_id", str(f))
            records.append(MemoryRecord(
                id=memory_id,
                content=body,
                scope=fm_meta.get("scope", "/"),
                categories=list(fm_meta.get("categories", [])),
                metadata={"source": fm_meta.get("source", "")},
                importance=fm_meta.get("importance", 0.5),
                source=fm_meta.get("source"),
            ))

        return records[offset : offset + limit]

    def get_scope_info(self, scope: str) -> ScopeInfo:
        files = self._glob_md(scope)
        categories: set[str] = set()
        oldest: datetime | None = None
        newest: datetime | None = None
        child_scopes: set[str] = set()

        for f in files:
            fm_meta, _ = self._read_md(f)
            for cat in fm_meta.get("categories", []):
                categories.add(cat)
            ts_str = fm_meta.get("timestamp", "")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if oldest is None or ts < oldest:
                        oldest = ts
                    if newest is None or ts > newest:
                        newest = ts
                except ValueError:
                    pass
            # Collect child scopes from dir structure
            rel = f.relative_to(self._scope_to_dir(scope))
            if os.sep in str(rel):
                child_scopes.add(str(rel).split(os.sep)[0])

        return ScopeInfo(
            path=scope,
            record_count=len(files),
            categories=list(categories),
            oldest_record=oldest,
            newest_record=newest,
            child_scopes=list(child_scopes),
        )

    def list_scopes(self, parent: str = "/") -> list[str]:
        parent_path = self._scope_to_dir(parent)
        if not parent_path.exists():
            return []
        scopes: set[str] = set()
        for item in parent_path.iterdir():
            if item.is_dir():
                child = f"{parent.rstrip('/')}/{item.name}"
                scopes.add(child)
        return sorted(scopes)

    def list_categories(
        self, scope_prefix: str | None = None
    ) -> dict[str, int]:
        scope = scope_prefix or "/"
        files = self._glob_md(scope)
        counts: dict[str, int] = {}
        for f in files:
            fm_meta, _ = self._read_md(f)
            for cat in fm_meta.get("categories", []):
                counts[cat] = counts.get(cat, 0) + 1
        return counts

    def count(self, scope_prefix: str | None = None) -> int:
        scope = scope_prefix or "/"
        return len(self._glob_md(scope))

    def reset(self, scope_prefix: str | None = None) -> None:
        scope = scope_prefix or "/"
        for f in self._glob_md(scope):
            f.unlink(missing_ok=True)
        self._collection.delete(where={"scope": {"$starts_with": scope}})

    # ------------------------------------------------------------------
    # Async variants (simple pass-through for now)
    # ------------------------------------------------------------------

    async def asave(self, records: List[MemoryRecord]) -> None:
        self.save(records)

    async def asearch(
        self,
        query_embedding: List[float],
        scope_prefix: str | None = None,
        categories: List[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> List[tuple[MemoryRecord, float]]:
        return self.search(
            query_embedding, scope_prefix, categories,
            metadata_filter, limit, min_score,
        )

    async def adelete(
        self,
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        record_ids: list[str] | None = None,
        older_than: datetime | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> int:
        return self.delete(scope_prefix, categories, record_ids, older_than, metadata_filter)


# ------------------------------------------------------------------
# FileMemory — CrewAI Memory subclass with file-based storage
# ------------------------------------------------------------------


class FileMemory(Memory):
    """
    CrewAI Memory subclass that uses FileStorageBackend.

    Usage:
        memory = FileMemory()
        memory.remember(content, scope="/global/searcher", source="agent")
        results = memory.recall("suppliers Nigeria", scope="/global/searcher")
        scoped = memory.scope("/agent/searcher")
    """

    _storage: FileStorageBackend

    def __init__(
        self,
        storage_dir: str | None = None,
        **kwargs,
    ):
        # Use model_construct to create Memory without running __init__ validators
        # (avoids LanceDB auto-initialization in model_post_init)
        obj = Memory.model_construct(
            llm=kwargs.get("llm", "gpt-4o-mini"),
            storage=kwargs.get("storage", "lancedb"),  # placeholder
            embedder=kwargs.get("embedder"),
            root_scope=kwargs.get("root_scope"),
            read_only=kwargs.get("read_only", False),
            recency_weight=kwargs.get("recency_weight", 0.3),
            semantic_weight=kwargs.get("semantic_weight", 0.5),
            importance_weight=kwargs.get("importance_weight", 0.2),
        )

        # Inject FileStorageBackend as storage
        object.__setattr__(obj, "_storage", FileStorageBackend(storage_dir=storage_dir))

        # Use our custom embedder for CrewAI internal EncodingFlow
        object.__setattr__(obj, "_embedder_instance", _ChromaEmbeddingFunction())

        # Required private attributes that model_construct doesn't set
        object.__setattr__(obj, "_save_pool", ThreadPoolExecutor(max_workers=1, thread_name_prefix="memory-save"))
        object.__setattr__(obj, "_pending_saves", [])
        object.__setattr__(obj, "_pending_lock", threading.Lock())

        # Copy Pydantic model attributes to self
        object.__setattr__(self, "__dict__", obj.__dict__)
        object.__setattr__(
            self,
            "__pydantic_fields_set__",
            getattr(obj, "__pydantic_fields_set__", set()),
        )
        # Pydantic v2 needs __pydantic_private__
        object.__setattr__(
            self,
            "__pydantic_private__",
            getattr(obj, "__pydantic_private__", {}),
        )

    # Expose storage_dir property
    @property
    def storage_dir(self) -> Path:
        return self._storage._storage_dir


# ------------------------------------------------------------------
# HybridMemory — FileMemory subclass bridging CrewAI recall to BM25
# ------------------------------------------------------------------


class HybridMemory(FileMemory):
    """
    FileMemory subclass that enables BM25 scoring in hybrid retrieval.

    CrewAI Memory.recall() only passes query_embedding to storage.search(),
    not the raw text. This class bridges that gap by:
    1. Capturing the raw query in recall()
    2. Passing it as a categories entry: [query_text]
    3. FileStorageBackend.search() then uses categories[0] as BM25 query

    Usage:
        memory = HybridMemory()
        # Agent calls: memory.recall("solar suppliers Nigeria")
        # → HybridMemory.recall() stores raw query, passes [query] as categories
        # → FileStorageBackend.search() uses query for BM25 + embedding for vector
    """

    def __init__(self, storage_dir: str | None = None, **kwargs):
        super().__init__(storage_dir=storage_dir, **kwargs)
        self._last_raw_query: str = ""

    def recall(
        self,
        query: str,
        scope: str | None = None,
        categories: list[str] | None = None,
        limit: int = 10,
        depth: Literal["shallow", "deep"] = "deep",
        source: str | None = None,
        include_private: bool = False,
    ) -> list[Any]:
        # Capture raw query for BM25 scoring in storage.search()
        self._last_raw_query = query
        # Pass raw query as first categories entry for BM25
        enhanced_categories = [query] if query else []
        if categories:
            enhanced_categories.extend(categories)
        return super().recall(
            query=query,
            scope=scope,
            categories=enhanced_categories,
            limit=limit,
            depth=depth,
            source=source,
            include_private=include_private,
        )
