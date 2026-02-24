"""Search functionality: FTS5 text search and cosine similarity for AI search."""

from __future__ import annotations

import numpy as np
import structlog

from .config import Config
from .db import Database
from .models import SearchResult
from .processing.embeddings import EmbeddingClient

log = structlog.get_logger()


class SearchEngine:
    def __init__(self, config: Config, db: Database) -> None:
        self.config = config
        self.db = db
        self._embedding_client: EmbeddingClient | None = None
        if config.ai.enabled:
            self._embedding_client = EmbeddingClient(config)

    def text_search(self, query: str, limit: int = 50) -> list[SearchResult]:
        """Full-text search using FTS5 with BM25 ranking."""
        if not query.strip():
            return []

        # Escape FTS5 special characters for safety
        fts_query = query.strip()

        results = self.db.search_fts(fts_query, limit=limit)

        # Group by screenshot_id, keep best rank
        seen: dict[int, dict] = {}
        for r in results:
            sid = r["screenshot_id"]
            if sid not in seen or r["rank"] < seen[sid]["rank"]:
                seen[sid] = r

        search_results = []
        for sid, r in seen.items():
            screenshot = self.db.get_screenshot(sid)
            if screenshot:
                search_results.append(SearchResult(
                    screenshot=screenshot,
                    ocr_text=r["text"],
                    score=-r["rank"],  # BM25 returns negative scores, negate for sorting
                    highlights=[r["snippet"]] if r.get("snippet") else [],
                ))

        search_results.sort(key=lambda x: x.score, reverse=True)
        return search_results

    async def ai_search(self, query: str, limit: int = 20) -> list[SearchResult]:
        """Semantic search using embedding cosine similarity."""
        if not self._embedding_client:
            return []

        query_vec = await self._embedding_client.embed(query)
        if query_vec is None:
            return []

        all_embeddings = self.db.get_all_embeddings()
        if not all_embeddings:
            return []

        # Compute cosine similarities
        scores: dict[int, float] = {}
        for sid, blob in all_embeddings:
            vec = EmbeddingClient.blob_to_vector(blob)
            sim = _cosine_similarity(query_vec, vec)
            if sid not in scores or sim > scores[sid]:
                scores[sid] = sim

        # Sort by similarity
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]

        results = []
        for sid, score in top:
            screenshot = self.db.get_screenshot(sid)
            if screenshot:
                ocr_text = self.db.get_ocr_text(sid)
                results.append(SearchResult(
                    screenshot=screenshot,
                    ocr_text=ocr_text,
                    score=score,
                ))

        return results


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(dot / norm)
