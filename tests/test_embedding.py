"""Unit tests for the embedding client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from normacore.embedding import EmbeddingClient


@pytest.fixture
def mock_httpx_client():
    """Provide a mocked httpx.AsyncClient."""
    with patch("normacore.embedding.httpx.AsyncClient") as mock:
        client_instance = AsyncMock()
        mock.return_value.__aenter__ = AsyncMock(return_value=client_instance)
        mock.return_value.__aexit__ = AsyncMock(return_value=False)
        yield client_instance


def make_mock_response(embedding: list[float]) -> MagicMock:
    """Build a mock httpx response returning the given embedding vector."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"embeddings": [embedding]}  # list[list[float]]
    return response


@pytest.mark.asyncio
async def test_embed_single_string(mock_httpx_client):
    """Test embedding a single string returns one vector."""
    mock_httpx_client.post = AsyncMock(return_value=make_mock_response([0.1] * 1024))

    client = EmbeddingClient()
    result = await client.embed("test sentence")

    assert len(result) == 1
    assert len(result[0]) == 1024
    mock_httpx_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_embed_multiple_strings(mock_httpx_client):
    """Test embedding a list of strings returns one vector per input."""
    mock_httpx_client.post = AsyncMock(return_value=make_mock_response([0.1] * 1024))

    client = EmbeddingClient()
    result = await client.embed(["first sentence", "second sentence", "third sentence"])

    assert len(result) == 3
    assert mock_httpx_client.post.call_count == 3


@pytest.mark.asyncio
async def test_embed_raises_on_http_error(mock_httpx_client):
    """Test that HTTP errors from the embedding service are propagated."""
    import httpx

    mock_httpx_client.post = AsyncMock(
        return_value=MagicMock(
            raise_for_status=MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "500 Server Error",
                    request=MagicMock(),
                    response=MagicMock(),
                )
            )
        )
    )

    client = EmbeddingClient()
    with pytest.raises(httpx.HTTPStatusError):
        await client.embed("test sentence")


@pytest.mark.asyncio
async def test_embed_response_model_validation(mock_httpx_client):
    """Test that the response is correctly parsed into EmbeddingResponse."""
    vector = [float(i) / 1024 for i in range(1024)]
    mock_httpx_client.post = AsyncMock(return_value=make_mock_response(vector))

    client = EmbeddingClient()
    result = await client.embed("test sentence")

    assert result[0] == vector
