"""FastAPI application for NormaCore retrieval service.

Exposes three endpoints:
- POST /v1/retrieve  — query a corpus and return ranked chunks
- GET  /v1/corpora   — list available corpora
- GET  /v1/health    — liveness healthcheck
"""

import argparse
import logging
import time

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

from normacore.config import settings
from normacore.embedding import EmbeddingClient
from normacore.logging import configure_logging
from normacore.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)

app = FastAPI(
    title="NormaCore",
    description="Self-hostable RAG ingestion and retrieval platform for structured documents.",
    version="0.1.0",
)
router = APIRouter(prefix="/v1")


class RetrieveRequest(BaseModel):
    """Request body for POST /retrieve.

    Attributes:
        corpus_id: Target corpus to query.
        query: Plain text query string.
        top_k: Number of results to return. Defaults to 5.
        alpha: Dense weight in hybrid fusion. Defaults to 0.7.
    """

    corpus_id: str
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    alpha: float = Field(default=0.7, ge=0.0, le=1.0)


class ChunkResult(BaseModel):
    """A single ranked retrieval result.

    Attributes:
        text: Chunk body text including heading path prefix.
        score: Relevance score from the vector store.
        metadata: Chunk metadata including corpus_id, section_id,
            heading_path, and source.
    """

    text: str
    score: float
    metadata: dict


class RetrieveResponse(BaseModel):
    """Response body for POST /retrieve.

    Attributes:
        results: Ranked list of chunk results.
        query_time_ms: Total retrieval time in milliseconds.
    """

    results: list[ChunkResult]
    query_time_ms: float


class HealthResponse(BaseModel):
    """Response body for GET /health.

    Attributes:
        status: Always 'ok' when the service is running.
    """

    status: str


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(request: RetrieveRequest) -> RetrieveResponse:
    """Query a corpus and return ranked chunks.

    Args:
        request: Retrieve request with corpus_id, query, top_k, and alpha.

    Returns:
        RetrieveResponse with ranked chunks and query time.

    Raises:
        HTTPException: 404 if the corpus does not exist in the vector store.
        HTTPException: 500 if the embedding service or vector store is unavailable.
    """
    logger.info(
        "Retrieve request — corpus: %s, query: %.60s, top_k: %s",
        request.corpus_id,
        request.query,
        request.top_k,
    )

    start = time.perf_counter()

    try:
        embedding_client = EmbeddingClient()
        vectors = await embedding_client.embed(request.query)
        query_vector = vectors[0]
    except Exception as exc:
        logger.exception("Embedding service error: %s", exc)
        raise HTTPException(
            status_code=500, detail="Embedding service unavailable."
        ) from exc

    try:
        vector_store = QdrantVectorStore()
        raw_results = await vector_store.search_hybrid(
            corpus_id=request.corpus_id,
            query_vector=query_vector,
            query_text=request.query,
            top_k=request.top_k,
            alpha=request.alpha,
        )
    except Exception as exc:
        logger.exception("Vector store error: %s", exc)
        raise HTTPException(
            status_code=404,
            detail="Corpus '%s' not found or vector store unavailable."
            % request.corpus_id,
        ) from exc

    elapsed_ms = (time.perf_counter() - start) * 1000

    results = [
        ChunkResult(
            text=r["text"],
            score=r["score"],
            metadata=r["metadata"],
        )
        for r in raw_results
    ]

    logger.info(
        "Retrieve complete — corpus: %s, results: %s, time: %.1fms",
        request.corpus_id,
        len(results),
        elapsed_ms,
    )

    return RetrieveResponse(results=results, query_time_ms=elapsed_ms)


@router.get("/corpora", response_model=list[str])
async def list_corpora() -> list[str]:
    """List all available corpus IDs in the vector store.

    Returns:
        List of corpus ID strings.

    Raises:
        HTTPException: 500 if the vector store is unavailable.
    """
    try:
        vector_store = QdrantVectorStore()
        collections = await vector_store.list_collections()
        return collections
    except Exception as exc:
        logger.exception("Vector store error listing corpora: %s", exc)
        raise HTTPException(
            status_code=500, detail="Vector store unavailable."
        ) from exc


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness healthcheck.

    Returns:
        HealthResponse with status 'ok'.
    """
    return HealthResponse(status="ok")


app.include_router(router)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace with host, port, and reload flag.
    """
    parser = argparse.ArgumentParser(description="Start the NormaCore API server.")
    parser.add_argument(
        "--host",
        type=str,
        default=settings.api_host,
        help="Host to bind the server to (default: from API_HOST env var).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.api_port,
        help="Port to bind the server to (default: from API_PORT env var).",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=False,
        help="Enable hot reload for development (do not use in production).",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for the API server."""
    import uvicorn

    configure_logging(settings.log_file, settings.log_level)
    args = parse_args()

    uvicorn.run(
        "normacore.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
