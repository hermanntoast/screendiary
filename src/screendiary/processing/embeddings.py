"""OpenAI-compatible embedding API client."""

from __future__ import annotations

import hashlib

import numpy as np
import structlog
from openai import AsyncOpenAI

from ..config import Config

log = structlog.get_logger()


class EmbeddingClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = AsyncOpenAI(
            base_url=config.ai.api_base,
            api_key=config.ai.api_key or "unused",
        )
        self.model = config.ai.embedding_model
        self._disabled = False

    async def embed(self, text: str) -> np.ndarray | None:
        """Get embedding vector for text. Returns numpy array or None on failure."""
        if self._disabled or not text.strip():
            return None
        try:
            resp = await self.client.embeddings.create(
                model=self.model,
                input=text[:8000],  # Truncate very long texts
            )
            vec = np.array(resp.data[0].embedding, dtype=np.float32)
            return vec
        except Exception as e:
            self._handle_embed_error(e)
            return None

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray | None]:
        """Embed multiple texts. Returns list of vectors (or None for failures)."""
        if self._disabled or not texts:
            return [None] * len(texts) if texts else []
        try:
            resp = await self.client.embeddings.create(
                model=self.model,
                input=[t[:8000] for t in texts],
            )
            results: list[np.ndarray | None] = [None] * len(texts)
            for item in resp.data:
                results[item.index] = np.array(item.embedding, dtype=np.float32)
            return results
        except Exception as e:
            self._handle_embed_error(e)
            return [None] * len(texts)

    def _handle_embed_error(self, e: Exception) -> None:
        """Handle embedding errors. Disable on 400/unsupported, log others."""
        err_str = str(e).lower()
        # Disable permanently for this session if the model can't do embeddings
        if any(kw in err_str for kw in (
            "does not support", "badrequest", "bad request",
            "not support embedding", "400",
        )):
            log.warning(
                "embeddings_disabled",
                model=self.model,
                reason=str(e)[:200],
            )
            self._disabled = True
        else:
            log.error("embedding_error", error=str(e)[:200])

    @staticmethod
    def text_hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    @staticmethod
    def vector_to_blob(vec: np.ndarray) -> bytes:
        return vec.tobytes()

    @staticmethod
    def blob_to_vector(blob: bytes) -> np.ndarray:
        return np.frombuffer(blob, dtype=np.float32)

    @staticmethod
    def chunk_text(text: str, max_tokens: int = 512, overlap: int = 50) -> list[str]:
        """Split text into overlapping chunks by word count."""
        words = text.split()
        if len(words) <= max_tokens:
            return [text] if text.strip() else []

        chunks = []
        start = 0
        while start < len(words):
            end = min(start + max_tokens, len(words))
            chunk = " ".join(words[start:end])
            if chunk.strip():
                chunks.append(chunk)
            start = end - overlap
            if start >= len(words) - overlap:
                break
        return chunks
