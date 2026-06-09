"""Vector store interface and Qdrant implementation."""

import logging
from abc import ABC, abstractmethod

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    Modifier,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from normacore.config import settings

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """Abstract interface for vector store backends."""

    @abstractmethod
    async def create_collection(self, corpus_id: str) -> None:
        """Create a new collection for a corpus.

        Args:
            corpus_id: Unique identifier for the corpus.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """

    @abstractmethod
    async def upsert_chunks(self, corpus_id: str, chunks: list[dict]) -> None:
        """Upsert a list of chunks into the collection.

        Args:
            corpus_id: Target collection identifier.
            chunks: List of chunk dicts with text, dense vector, and metadata.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """

    @abstractmethod
    async def search_hybrid(
        self,
        corpus_id: str,
        query_vector: list[float],
        query_text: str,
        top_k: int = 5,
        alpha: float = 0.7,
    ) -> list[dict]:
        """Run hybrid search and return ranked chunks.

        Args:
            corpus_id: Target collection identifier.
            query_vector: Dense query embedding.
            query_text: Raw query text for BM25 sparse search.
            top_k: Number of results to return.
            alpha: Weight for dense vs sparse (1.0 = dense only).

        Returns:
            List of chunk dicts with text, score, and metadata.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """

    @abstractmethod
    async def delete_collection(self, corpus_id: str) -> None:
        """Delete a collection and all its chunks.

        Args:
            corpus_id: Target collection identifier.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """


class QdrantVectorStore(VectorStore):
    """Qdrant implementation of the VectorStore interface."""

    def __init__(self) -> None:
        self._client = AsyncQdrantClient(url=settings.qdrant_url)

    async def create_collection(self, corpus_id: str) -> None:
        """Create a new collection for a corpus.

        Args:
            corpus_id: Unique identifier for the corpus.
        """
        logger.info("Creating collection %s", corpus_id)

        collections = await self._client.get_collections()
        existing = [c.name for c in collections.collections]

        if corpus_id in existing:
            logger.warning("Collection %s already exists, recreating", corpus_id)
            await self._client.delete_collection(corpus_id)

        await self._client.create_collection(
            collection_name=corpus_id,
            vectors_config={"dense": VectorParams(size=1024, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams(modifier=Modifier.IDF)},
        )
        logger.info("Collection %s created", corpus_id)

    async def upsert_chunks(self, corpus_id: str, chunks: list[dict]) -> None:
        """Upsert a list of chunks into the collection.

        Args:
            corpus_id: Target collection identifier.
            chunks: List of chunk dicts with text, dense vector, and metadata.
        """
        points = [
            PointStruct(
                id=chunk["chunk_index"],
                vector={
                    "dense": chunk["dense_vector"],
                    "sparse": SparseVector(
                        indices=chunk["sparse_indices"],
                        values=chunk["sparse_values"],
                    ),
                },
                payload={
                    "text": chunk["text"],
                    "corpus_id": corpus_id,
                    **chunk["metadata"],
                },
            )
            for chunk in chunks
        ]

        logger.info("Upserting %s chunks into collection %s", len(points), corpus_id)
        await self._client.upsert(collection_name=corpus_id, points=points)
        logger.info("Upserted %s chunks into %s successfully", len(points), corpus_id)

    async def search_hybrid(
        self,
        corpus_id: str,
        query_vector: list[float],
        query_text: str,
        top_k: int = 5,
        alpha: float = 0.7,
    ) -> list[dict]:
        """Run hybrid search and return ranked chunks."""
        logger.info(
            "Running hybrid search on %s (top_k=%s, alpha=%s)", corpus_id, top_k, alpha
        )

        results = await self._client.query_points(
            collection_name=corpus_id,
            query=query_vector,
            using="dense",
            limit=top_k,
        )

        chunks = [
            {
                "text": point.payload["text"],
                "score": point.score,
                "metadata": {k: v for k, v in point.payload.items() if k != "text"},
            }
            for point in results.points
        ]

        logger.info("Hybrid search returned %s results", len(chunks))
        return chunks

    async def delete_collection(self, corpus_id: str) -> None:
        """Delete a collection and all its chunks.

        Args:
            corpus_id: Unique identifier for the corpus.
        """
        logger.info("Deleting collection %s", corpus_id)
        await self._client.delete_collection(corpus_id)
        logger.info("Collection %s deleted", corpus_id)
