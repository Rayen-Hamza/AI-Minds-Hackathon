"""
Shadow Senses — File monitoring pipeline with Ledger Strategy.

Implements a differential ingestion system that tracks file state via an SQLite
ledger, computes per-chunk SHA-256 hashes, and only embeds/deletes the chunks
that actually changed.  A watchdog-based sentinel watches configured folders
and feeds changed paths into the pipeline.

Components
----------
LedgerState          – SQLite state management (the "Ledger")
LedgerIngestionService – Differential chunk logic (the "Brain")
ShadowSentinel       – watchdog-based folder watcher (the "Sentinel")
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import queue
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.config import settings
from app.services.storage import get_qdrant_manager
from app.services.embeddings import get_text_embedder
from app.services.processing import get_text_processor

from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchAny

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_LEDGER_DIR = Path("./data")
_DEFAULT_LEDGER_DB = _DEFAULT_LEDGER_DIR / "shadow_ledger.db"
_DEBOUNCE_SECONDS = 1.0  # ignore duplicate events within this window
_MAX_QUEUE_SIZE = 500  # cap the work queue to prevent unbounded memory growth
_WORKER_DRAIN_TIMEOUT = 10.0  # seconds to wait for the queue to drain on shutdown

# Supported text-based file extensions for automatic processing
_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".txt", ".md", ".pdf", ".py", ".js", ".ts", ".json", ".csv"}
)


class _ActionKind(Enum):
    """Type of work item enqueued by the sentinel."""
    PROCESS = auto()   # on_created / on_modified
    DELETE = auto()    # on_deleted
    SHUTDOWN = auto()  # poison pill to stop the worker


@dataclass(frozen=True)
class _WorkItem:
    """A unit of work pulled from the event queue."""
    action: _ActionKind
    path: str = ""


# ============================================================================
# 1. The Ledger  (State Management)
# ============================================================================


@dataclass
class FileState:
    """Snapshot of a tracked file's state in the Ledger."""

    file_path: str
    last_modified: float
    chunk_hashes: list[str] = field(default_factory=list)


class LedgerState:
    """
    SQLite-backed ledger that tracks per-file chunk hashes and timestamps.

    Database: ``./data/shadow_ledger.db``
    Table:    ``file_states``
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else _DEFAULT_LEDGER_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    # ----- bootstrap --------------------------------------------------------

    def _init_db(self) -> None:
        """Create the ``file_states`` table if it doesn't exist."""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS file_states (
                    file_path    TEXT PRIMARY KEY,
                    last_modified REAL NOT NULL,
                    chunk_hashes TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            conn.commit()
        logger.info(f"Ledger initialised at {self._db_path}")

    def _connect(self) -> sqlite3.Connection:
        """Return a new connection with WAL mode for concurrency."""
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    # ----- public API -------------------------------------------------------

    def get_state(self, path: str) -> Optional[FileState]:
        """
        Load the stored ``FileState`` for *path*, or ``None`` if unknown.

        Parameters
        ----------
        path : str
            Absolute or relative file path (normalised internally).

        Returns
        -------
        FileState | None
        """
        norm = self._normalise(path)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT file_path, last_modified, chunk_hashes FROM file_states WHERE file_path = ?",
                (norm,),
            ).fetchone()
            if row is None:
                return None
            return FileState(
                file_path=row["file_path"],
                last_modified=row["last_modified"],
                chunk_hashes=json.loads(row["chunk_hashes"]),
            )

    def update_state(
        self, path: str, modified: float, hashes: list[str]
    ) -> None:
        """
        Insert or replace the state for *path*.

        Parameters
        ----------
        path : str
            File path.
        modified : float
            ``os.path.getmtime`` result.
        hashes : list[str]
            SHA-256 hex digests for every chunk in the file.
        """
        norm = self._normalise(path)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO file_states (file_path, last_modified, chunk_hashes)
                VALUES (?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    last_modified = excluded.last_modified,
                    chunk_hashes  = excluded.chunk_hashes
                """,
                (norm, modified, json.dumps(hashes)),
            )
            conn.commit()
        logger.debug(f"Ledger updated: {norm}  ({len(hashes)} chunks)")

    def delete_state(self, path: str) -> None:
        """
        Remove the entry for *path* from the ledger.

        Parameters
        ----------
        path : str
            File path to purge.
        """
        norm = self._normalise(path)
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM file_states WHERE file_path = ?", (norm,))
            conn.commit()
        logger.debug(f"Ledger entry deleted: {norm}")

    def all_tracked_paths(self) -> list[str]:
        """Return every file path currently tracked by the ledger."""
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT file_path FROM file_states").fetchall()
            return [r["file_path"] for r in rows]

    # ----- helpers ----------------------------------------------------------

    @staticmethod
    def _normalise(path: str) -> str:
        """Canonical, OS-independent path representation."""
        return str(Path(path).resolve())


# ============================================================================
# 2. Differential Logic  (The Brain)
# ============================================================================


class LedgerIngestionService:
    """
    Differential ingestion engine.

    On file change:
      1. Read & chunk the file.
      2. SHA-256 each chunk's content.
      3. Compare with the ledger to find ``to_add`` / ``to_delete`` sets.
      4. Sync only the *delta* with Qdrant.
      5. Commit the new state to the ledger.
    """

    def __init__(
        self,
        ledger: LedgerState | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        self.ledger = ledger or LedgerState()

        # Re-use the project's TextProcessor for chunking
        self._text_processor = get_text_processor()

        # Override chunk params if requested
        if chunk_size is not None:
            self._text_processor.chunk_size = chunk_size
        if chunk_overlap is not None:
            self._text_processor.chunk_overlap = chunk_overlap

        # Lazy references — initialised on first use
        self._qdrant = None
        self._embedder = None

    # -- lazy accessors ------------------------------------------------------

    @property
    def qdrant(self):
        if self._qdrant is None:
            self._qdrant = get_qdrant_manager()
        return self._qdrant

    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = get_text_embedder()
        return self._embedder

    # -- public API ----------------------------------------------------------

    def process(self, path: str) -> dict:
        """
        Process a file change: compute the diff and sync with the vector DB.

        Parameters
        ----------
        path : str
            Path to the changed / created file.

        Returns
        -------
        dict
            Summary: ``{"added": int, "deleted": int, "unchanged": int}``
        """
        norm_path = str(Path(path).resolve())
        logger.info(f"[ShadowSenses] Processing: {norm_path}")

        # ---- Guard: file readability -----------------------------------
        if not self._is_readable(norm_path):
            logger.warning(f"[ShadowSenses] File unreadable or locked: {norm_path}")
            return {"added": 0, "deleted": 0, "unchanged": 0, "error": "unreadable"}

        # ---- Guard: empty file -----------------------------------------
        if os.path.getsize(norm_path) == 0:
            logger.info(f"[ShadowSenses] Empty file, skipping: {norm_path}")
            return {"added": 0, "deleted": 0, "unchanged": 0, "skipped": "empty"}

        # ---- Guard: unsupported extension ------------------------------
        ext = Path(norm_path).suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            logger.debug(f"[ShadowSenses] Unsupported extension {ext}, skipping.")
            return {"added": 0, "deleted": 0, "unchanged": 0, "skipped": "unsupported"}

        # ---- 1. Read & Chunk -------------------------------------------
        try:
            chunks = self._read_and_chunk(norm_path)
        except Exception as exc:
            logger.error(f"[ShadowSenses] Chunking failed for {norm_path}: {exc}")
            return {"added": 0, "deleted": 0, "unchanged": 0, "error": str(exc)}

        if not chunks:
            logger.info(f"[ShadowSenses] No chunks produced from {norm_path}")
            # If the file previously had content, treat as "everything deleted"
            self.handle_deletion(norm_path)
            return {"added": 0, "deleted": 0, "unchanged": 0, "skipped": "no_chunks"}

        # ---- 2. Hash every chunk content --------------------------------
        new_hashes: list[str] = [self._hash_chunk(c) for c in chunks]
        hash_to_chunk: dict[str, str] = dict(zip(new_hashes, chunks))

        # ---- 3. Compare with ledger ------------------------------------
        state = self.ledger.get_state(norm_path)
        old_hashes: set[str] = set(state.chunk_hashes) if state else set()
        new_hashes_set: set[str] = set(new_hashes)

        to_add = new_hashes_set - old_hashes
        to_delete = old_hashes - new_hashes_set
        unchanged = new_hashes_set & old_hashes

        logger.info(
            f"[ShadowSenses] Diff for {Path(norm_path).name}: "
            f"+{len(to_add)} -{len(to_delete)} ={len(unchanged)}"
        )

        # ---- 4. Sync Vector DB -----------------------------------------
        # 4a. Delete stale vectors
        if to_delete:
            self._delete_vectors(norm_path, to_delete)

        # 4b. Upsert new / edited chunk vectors
        if to_add:
            self._upsert_vectors(norm_path, to_add, hash_to_chunk)

        # ---- 5. Commit to Ledger ---------------------------------------
        mtime = os.path.getmtime(norm_path)
        self.ledger.update_state(norm_path, mtime, new_hashes)

        return {
            "added": len(to_add),
            "deleted": len(to_delete),
            "unchanged": len(unchanged),
        }

    def handle_deletion(self, path: str) -> dict:
        """
        Handle a file deletion: remove **all** its vectors + ledger entry.

        Parameters
        ----------
        path : str
            Path of the deleted file.

        Returns
        -------
        dict
            Summary: ``{"deleted": int}``
        """
        norm_path = str(Path(path).resolve())
        logger.info(f"[ShadowSenses] Handling deletion: {norm_path}")

        state = self.ledger.get_state(norm_path)
        deleted = 0

        if state and state.chunk_hashes:
            vector_ids = [
                self._deterministic_id(norm_path, h) for h in state.chunk_hashes
            ]
            try:
                self.qdrant.client.delete(
                    collection_name=settings.unified_collection,
                    points_selector=vector_ids,
                )
                deleted = len(vector_ids)
                logger.info(
                    f"[ShadowSenses] Deleted {deleted} vectors for {norm_path}"
                )
            except Exception as exc:
                logger.error(f"[ShadowSenses] Vector deletion failed: {exc}")

        self.ledger.delete_state(norm_path)
        return {"deleted": deleted}

    # -- internal helpers ----------------------------------------------------

    def _read_and_chunk(self, path: str) -> list[str]:
        """Read a file and return a list of text chunks."""
        file_path = Path(path)
        file_type = file_path.suffix.lstrip(".").lower()

        if file_type == "pdf":
            from app.services.processing import get_pdf_processor

            pdf = get_pdf_processor()
            text = pdf.extract_text(file_path)
        else:
            # Try reading with utf-8 first, fall back to latin-1
            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    text = fh.read()
            except UnicodeDecodeError:
                with open(file_path, "r", encoding="latin-1") as fh:
                    text = fh.read()

        if not text or not text.strip():
            return []

        return self._text_processor.chunk_text(text)

    @staticmethod
    def _hash_chunk(content: str) -> str:
        """SHA-256 hex digest of a chunk's raw content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _deterministic_id(file_path: str, chunk_hash: str) -> str:
        """
        Build a deterministic, reproducible vector ID from file path + chunk hash.

        Uses a SHA-256 hash of ``file_path || chunk_hash`` truncated to a
        64-char hex string — safe as a Qdrant point ID.
        """
        combined = f"{file_path}::{chunk_hash}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def _upsert_vectors(
        self,
        file_path: str,
        hashes_to_add: set[str],
        hash_to_chunk: dict[str, str],
    ) -> None:
        """Embed and upsert only the new / changed chunks."""
        chunks_to_embed: list[tuple[str, str, str]] = []  # (id, hash, text)
        for h in hashes_to_add:
            chunk_text = hash_to_chunk.get(h)
            if chunk_text is None:
                logger.warning(f"[ShadowSenses] Missing chunk for hash {h[:16]}…")
                continue
            vid = self._deterministic_id(file_path, h)
            chunks_to_embed.append((vid, h, chunk_text))

        if not chunks_to_embed:
            return

        texts = [c[2] for c in chunks_to_embed]

        # Batch embed
        try:
            embeddings = self.embedder.embed_batch(texts)
        except Exception as exc:
            logger.error(f"[ShadowSenses] Embedding failed: {exc}")
            raise

        # Build Qdrant points
        points: list[PointStruct] = []
        for (vid, h, chunk_text), embedding in zip(chunks_to_embed, embeddings):
            payload = {
                "source_path": file_path,
                "content_type": "text",
                "file_type": Path(file_path).suffix.lstrip(".").lower(),
                "chunk_text": chunk_text,
                "content_hash": h,
                "shadow_senses": True,  # mark origin
            }
            points.append(
                PointStruct(
                    id=vid,
                    vector={"text_vector": embedding},
                    payload=payload,
                )
            )

        try:
            self.qdrant.client.upsert(
                collection_name=settings.unified_collection,
                points=points,
            )
            logger.info(
                f"[ShadowSenses] Upserted {len(points)} vectors for "
                f"{Path(file_path).name}"
            )
        except Exception as exc:
            logger.error(f"[ShadowSenses] Qdrant upsert failed: {exc}")
            raise

    def _delete_vectors(self, file_path: str, hashes_to_delete: set[str]) -> None:
        """Remove vectors whose chunk hashes are no longer present."""
        ids = [self._deterministic_id(file_path, h) for h in hashes_to_delete]
        try:
            self.qdrant.client.delete(
                collection_name=settings.unified_collection,
                points_selector=ids,
            )
            logger.info(
                f"[ShadowSenses] Deleted {len(ids)} stale vectors for "
                f"{Path(file_path).name}"
            )
        except Exception as exc:
            logger.error(f"[ShadowSenses] Qdrant delete failed: {exc}")
            raise

    @staticmethod
    def _is_readable(path: str) -> bool:
        """
        Check if a file exists and is readable (not locked).

        Tries to open the file briefly; catches ``PermissionError`` and
        ``OSError`` for locked files on Windows / Linux.
        """
        try:
            with open(path, "rb") as fh:
                fh.read(1)
            return True
        except (PermissionError, OSError, FileNotFoundError):
            return False


# ============================================================================
# 3. The Sentinel  (The Watcher)
# ============================================================================


class _DebouncedHandler(FileSystemEventHandler):
    """
    Internal ``watchdog`` event handler with per-path debounce.

    Instead of processing on the watchdog thread (which would block
    subsequent events while an embedding call runs), events are
    validated / debounced and then pushed onto a ``queue.Queue``
    for asynchronous consumption by a background worker.
    """

    def __init__(self, work_queue: queue.Queue) -> None:
        super().__init__()
        self._queue = work_queue
        self._last_fired: dict[str, float] = {}
        self._lock = threading.Lock()

    # -- helpers -------------------------------------------------------------

    def _should_process(self, path: str) -> bool:
        """Return True only if the debounce window has elapsed for *path*."""
        now = time.time()
        with self._lock:
            last = self._last_fired.get(path, 0.0)
            if now - last < _DEBOUNCE_SECONDS:
                return False
            self._last_fired[path] = now
            return True

    @staticmethod
    def _is_supported(path: str) -> bool:
        ext = Path(path).suffix.lower()
        return ext in _SUPPORTED_EXTENSIONS

    def _enqueue(self, action: _ActionKind, path: str) -> None:
        """Push a work item; drop if the queue is full (back-pressure)."""
        try:
            self._queue.put_nowait(_WorkItem(action=action, path=path))
        except queue.Full:
            logger.warning(
                f"[Sentinel] Queue full ({_MAX_QUEUE_SIZE}), dropping event: {path}"
            )

    # -- watchdog callbacks --------------------------------------------------

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = str(event.src_path)
        if not self._is_supported(path):
            return
        if not self._should_process(path):
            return
        logger.info(f"[Sentinel] File created  → queued: {path}")
        self._enqueue(_ActionKind.PROCESS, path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = str(event.src_path)
        if not self._is_supported(path):
            return
        if not self._should_process(path):
            return
        logger.info(f"[Sentinel] File modified → queued: {path}")
        self._enqueue(_ActionKind.PROCESS, path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = str(event.src_path)
        if not self._is_supported(path):
            return
        if not self._should_process(path):
            return
        logger.info(f"[Sentinel] File deleted  → queued: {path}")
        self._enqueue(_ActionKind.DELETE, path)


class ShadowSentinel:
    """
    Folder watcher that feeds file-system events into ``LedgerIngestionService``
    through a bounded ``queue.Queue`` and a background worker thread.

    Architecture
    ------------
    ::

        watchdog observer
              │  (fast — never blocks)
              ▼
        _DebouncedHandler  ──▶  queue.Queue(maxsize=500)
                                       │
                                       ▼
                               _worker thread  ──▶  LedgerIngestionService

    This ensures that:
    * The watchdog thread is never blocked by slow embedding / DB calls.
    * Multiple rapid events are debounced *and* serialised.
    * Back-pressure is applied when the queue is full (events are dropped
      with a warning rather than blocking the OS-level file notifier).

    Usage
    -----
    >>> sentinel = ShadowSentinel(watch_paths=["./docs", "./notes"])
    >>> sentinel.start()
    >>> # …
    >>> sentinel.stop()

    Or as a context manager:

    >>> with ShadowSentinel(watch_paths=["./docs"]) as sentinel:
    ...     time.sleep(60)
    """

    def __init__(
        self,
        watch_paths: list[str | Path] | None = None,
        recursive: bool = False,
        ingestion_service: LedgerIngestionService | None = None,
        max_queue_size: int = _MAX_QUEUE_SIZE,
        num_workers: int = 1,
    ) -> None:
        """
        Parameters
        ----------
        watch_paths : list[str | Path]
            Directories to observe.  Defaults to ``["./data/watched"]``.
        recursive : bool
            Whether to watch sub-directories.  Defaults to False for safety.
        ingestion_service : LedgerIngestionService | None
            Optional pre-configured service; one is created if omitted.
        max_queue_size : int
            Maximum pending work items before back-pressure kicks in.
        num_workers : int
            Number of consumer threads.  Keep at 1 unless your embedding
            pipeline is thread-safe *and* you want parallelism.
        """
        if watch_paths is None:
            watch_paths = [Path("./data/watched")]

        self._watch_paths = [Path(p) for p in watch_paths]
        self._recursive = recursive
        self._service = ingestion_service or LedgerIngestionService()
        self._num_workers = max(1, num_workers)

        # Bounded work queue
        self._queue: queue.Queue[_WorkItem] = queue.Queue(maxsize=max_queue_size)

        self._handler = _DebouncedHandler(self._queue)
        self._observer = Observer()
        self._workers: list[threading.Thread] = []
        self._running = False

        # Ensure watched directories exist
        for wp in self._watch_paths:
            wp.mkdir(parents=True, exist_ok=True)

    # -- worker loop ---------------------------------------------------------

    def _worker_loop(self) -> None:
        """Background thread that drains the queue and dispatches work."""
        logger.info("[Sentinel-Worker] Started.")
        while True:
            try:
                item: _WorkItem = self._queue.get(timeout=1.0)
            except queue.Empty:
                # No work — loop back and check again (allows clean shutdown)
                continue

            if item.action is _ActionKind.SHUTDOWN:
                self._queue.task_done()
                logger.info("[Sentinel-Worker] Received shutdown signal.")
                break

            try:
                if item.action is _ActionKind.PROCESS:
                    result = self._service.process(item.path)
                    logger.debug(f"[Sentinel-Worker] Processed {item.path}: {result}")
                elif item.action is _ActionKind.DELETE:
                    result = self._service.handle_deletion(item.path)
                    logger.debug(f"[Sentinel-Worker] Deleted {item.path}: {result}")
            except Exception as exc:
                logger.error(
                    f"[Sentinel-Worker] Failed to handle {item.action.name} "
                    f"for {item.path}: {exc}",
                    exc_info=True,
                )
            finally:
                self._queue.task_done()

        logger.info("[Sentinel-Worker] Exiting.")

    # -- public API ----------------------------------------------------------

    def start(self) -> None:
        """Begin observing all configured paths and start the worker(s)."""
        if self._running:
            logger.warning("[Sentinel] Already running.")
            return

        # Schedule watches
        for wp in self._watch_paths:
            resolved = str(wp.resolve())
            self._observer.schedule(
                self._handler, resolved, recursive=self._recursive
            )
            logger.info(
                f"[Sentinel] Watching: {resolved}  (recursive={self._recursive})"
            )

        # Start worker thread(s)
        for idx in range(self._num_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"ShadowSentinel-Worker-{idx}",
                daemon=True,
            )
            t.start()
            self._workers.append(t)

        self._observer.start()
        self._running = True
        logger.info(
            f"[Sentinel] Started with {self._num_workers} worker(s) "
            f"and queue capacity {self._queue.maxsize}."
        )

    def stop(self, drain: bool = True) -> None:
        """
        Stop the observer and worker(s) gracefully.

        Parameters
        ----------
        drain : bool
            If True (default), wait up to ``_WORKER_DRAIN_TIMEOUT`` seconds
            for in-flight items to finish before sending the shutdown signal.
        """
        if not self._running:
            return
        logger.info("[Sentinel] Stopping…")

        # 1. Stop the watchdog observer first (no new events)
        self._observer.stop()
        self._observer.join(timeout=5)

        # 2. Optionally wait for the queue to drain
        if drain:
            logger.info(
                f"[Sentinel] Draining queue ({self._queue.qsize()} items)…"
            )
            try:
                self._queue.join()  # blocks until task_done for every item
            except Exception:
                pass

        # 3. Send shutdown poison pills
        for _ in self._workers:
            try:
                self._queue.put_nowait(
                    _WorkItem(action=_ActionKind.SHUTDOWN)
                )
            except queue.Full:
                pass  # worker will exit on its next timeout anyway

        # 4. Join worker threads
        for t in self._workers:
            t.join(timeout=_WORKER_DRAIN_TIMEOUT)

        self._workers.clear()
        self._running = False
        logger.info("[Sentinel] Stopped.")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def queue_size(self) -> int:
        """Current number of pending items in the work queue."""
        return self._queue.qsize()

    @property
    def ingestion_service(self) -> LedgerIngestionService:
        """Expose the ingestion service for manual calls."""
        return self._service

    # -- context manager -----------------------------------------------------

    def __enter__(self) -> "ShadowSentinel":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()


# ============================================================================
# Module-level singletons
# ============================================================================

_ledger_state: Optional[LedgerState] = None
_ingestion_service: Optional[LedgerIngestionService] = None
_shadow_sentinel: Optional[ShadowSentinel] = None


def get_ledger_state() -> LedgerState:
    """Get or create the global LedgerState singleton."""
    global _ledger_state
    if _ledger_state is None:
        _ledger_state = LedgerState()
    return _ledger_state


def get_ingestion_service() -> LedgerIngestionService:
    """Get or create the global LedgerIngestionService singleton."""
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = LedgerIngestionService(ledger=get_ledger_state())
    return _ingestion_service


def get_shadow_sentinel(
    watch_paths: list[str | Path] | None = None,
    recursive: bool = False,
) -> ShadowSentinel:
    """Get or create the global ShadowSentinel singleton."""
    global _shadow_sentinel
    if _shadow_sentinel is None:
        _shadow_sentinel = ShadowSentinel(
            watch_paths=watch_paths,
            recursive=recursive,
            ingestion_service=get_ingestion_service(),
        )
    return _shadow_sentinel
