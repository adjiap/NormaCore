"""Async HTTP client for the embedding service."""

import logging

import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from normacore.config import settings

logger = logging.getLogger(__name__)


class EmbeddingRequest(BaseModel):
    """Request model for the embedding service."""

    model: str
    input: str


class EmbeddingResponse(BaseModel):
    """Response model for the embedding service."""

    embeddings: list[list[float]]


class EmbeddingClient:
    """Async client wrapping the Ollama embeddings endpoint."""

    def __init__(self) -> None:
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def embed(self, text: str | list[str]) -> list[list[float]]:
        """Embed one or more strings.

        Args:
            text: A single string or list of strings to embed.

        Returns:
            A list of dense embedding vectors, one per input string.

        Raises:
            httpx.HTTPError: If the embedding service returns an error.
        """
        inputs = [text] if isinstance(text, str) else text
        logger.debug("Embedding %s input(s)", len(inputs))

        results: list[list[float]] = []

        async with httpx.AsyncClient() as client:
            for input_text in inputs:
                request = EmbeddingRequest(
                    model=settings.embedding_model,
                    input=input_text,
                )
                response = await client.post(
                    f"{settings.embedding_base_url}/api/embed",
                    json=request.model_dump(),
                )
                response.raise_for_status()
                parsed = EmbeddingResponse.model_validate(response.json())
                logger.debug(
                    "Received embedding of dimension %s", len(parsed.embeddings)
                )
                results.append(parsed.embeddings[0])

        logger.debug("Embedded %s input(s) successfully", len(results))
        return results
