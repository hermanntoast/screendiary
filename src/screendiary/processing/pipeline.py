"""Async processing pipeline: OCR -> FTS5 -> Embeddings."""

from __future__ import annotations

import asyncio

import structlog
from PIL import Image

from ..config import Config
from ..db import Database
from ..models import Embedding, OCRResult, OCRWord
from .embeddings import EmbeddingClient
from .ocr import ocr_image_async

log = structlog.get_logger()


class ProcessingPipeline:
    def __init__(self, config: Config, db: Database) -> None:
        self.config = config
        self.db = db
        self.queue: asyncio.Queue[tuple[int, list[tuple[int, Image.Image]]]] = asyncio.Queue()
        self._running = False
        self._workers: list[asyncio.Task] = []
        self._embedding_client: EmbeddingClient | None = None

    async def start(self) -> None:
        self._running = True
        if self.config.ai.enabled:
            self._embedding_client = EmbeddingClient(self.config)

        for i in range(self.config.ocr.workers):
            task = asyncio.create_task(self._worker(i))
            self._workers.append(task)
        log.info("pipeline_started", workers=self.config.ocr.workers)

    async def stop(self) -> None:
        self._running = False
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def enqueue(
        self, screenshot_id: int, monitor_images: list[tuple[int, Image.Image]]
    ) -> None:
        """Enqueue a screenshot for OCR processing.
        monitor_images: list of (monitor_capture_id, PIL.Image)
        """
        await self.queue.put((screenshot_id, monitor_images))

    async def _worker(self, worker_id: int) -> None:
        log.info("pipeline_worker_started", worker=worker_id)
        while self._running:
            try:
                screenshot_id, monitor_images = await asyncio.wait_for(
                    self.queue.get(), timeout=1.0
                )
            except (TimeoutError, asyncio.TimeoutError):
                continue
            except asyncio.CancelledError:
                break

            try:
                await self._process(screenshot_id, monitor_images)
            except Exception as e:
                log.error("pipeline_process_error", error=str(e), screenshot_id=screenshot_id)

    async def _process(
        self, screenshot_id: int, monitor_images: list[tuple[int, Image.Image]]
    ) -> None:
        """Process a screenshot: OCR each monitor, store results, compute embeddings."""
        all_text_parts = []

        for mc_id, image in monitor_images:
            text, confidence, word_boxes = await ocr_image_async(image, self.config)

            if len(text) < self.config.ocr.min_text_length:
                continue

            ocr = OCRResult(
                screenshot_id=screenshot_id,
                monitor_capture_id=mc_id,
                text=text,
                language=self.config.ocr.languages,
                confidence=confidence,
            )
            ocr_result_id = self.db.insert_ocr_result(ocr)

            # Save word-level bounding boxes
            if word_boxes:
                ocr_words = [
                    OCRWord(
                        ocr_result_id=ocr_result_id,
                        monitor_capture_id=mc_id,
                        word=wb["word"],
                        left=wb["left"],
                        top=wb["top"],
                        width=wb["width"],
                        height=wb["height"],
                        confidence=wb["confidence"],
                    )
                    for wb in word_boxes
                ]
                self.db.insert_ocr_words(ocr_words)

            all_text_parts.append(text)

        # Embeddings
        if all_text_parts and self._embedding_client and self.config.ai.enabled:
            combined = "\n\n".join(all_text_parts)
            text_hash = EmbeddingClient.text_hash(combined)

            if not self.db.has_embedding(screenshot_id, text_hash):
                chunks = EmbeddingClient.chunk_text(
                    combined, max_tokens=self.config.ai.chunk_max_tokens
                )
                if chunks:
                    vectors = await self._embedding_client.embed_batch(chunks)
                    for vec in vectors:
                        if vec is not None:
                            emb = Embedding(
                                screenshot_id=screenshot_id,
                                vector=EmbeddingClient.vector_to_blob(vec),
                                model=self.config.ai.embedding_model,
                                dimensions=len(vec),
                                text_hash=text_hash,
                            )
                            self.db.insert_embedding(emb)

        log.debug(
            "screenshot_processed",
            screenshot_id=screenshot_id,
            text_parts=len(all_text_parts),
        )
