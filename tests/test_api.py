"""Smoke tests for the NormaCore FastAPI application."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from normacore.api import app

BASE_URL = "http://test"


@pytest.fixture
def mock_embedding_client():
    """Provide a mocked EmbeddingClient."""
    with patch("normacore.api.EmbeddingClient") as mock:
        instance = AsyncMock()
        instance.embed.return_value = [[0.1] * 1024]
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_vector_store():
    """Provide a mocked QdrantVectorStore."""
    with patch("normacore.api.QdrantVectorStore") as mock:
        instance = AsyncMock()
        instance.search_hybrid.return_value = [
            {
                "text": "1 Scope\n\nThis document specifies requirements.",
                "score": 0.91,
                "metadata": {
                    "corpus_id": "test-corpus",
                    "section_id": "1",
                    "heading_path": ["1 Scope"],
                    "source": "sample-standard",
                },
            }
        ]
        instance.list_collections.return_value = ["test-corpus", "iso-26262"]
        mock.return_value = instance
        yield instance


@pytest.fixture
def client():
    """Provide an async test client for the FastAPI app."""
    return AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)


class TestHealth:

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        """GET /v1/health returns status ok."""
        async with client as c:
            response = await c.get("/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestListCorpora:

    @pytest.mark.asyncio
    async def test_list_corpora_returns_names(self, client, mock_vector_store):
        """GET /v1/corpora returns list of corpus IDs."""
        async with client as c:
            response = await c.get("/v1/corpora")
        assert response.status_code == 200
        assert response.json() == ["test-corpus", "iso-26262"]

    @pytest.mark.asyncio
    async def test_list_corpora_vector_store_error(self, client, mock_vector_store):
        """GET /v1/corpora returns 500 when vector store is unavailable."""
        mock_vector_store.list_collections.side_effect = Exception("connection refused")
        async with client as c:
            response = await c.get("/v1/corpora")
        assert response.status_code == 500


class TestRetrieve:

    @pytest.mark.asyncio
    async def test_retrieve_returns_chunks(
        self, client, mock_embedding_client, mock_vector_store
    ):
        """POST /v1/retrieve returns ranked chunks with metadata."""
        async with client as c:
            response = await c.post(
                "/v1/retrieve",
                json={"corpus_id": "test-corpus", "query": "What is the scope?"},
            )
        assert response.status_code == 200
        body = response.json()
        assert len(body["results"]) == 1
        assert body["results"][0]["score"] == 0.91
        assert body["results"][0]["metadata"]["corpus_id"] == "test-corpus"
        assert "query_time_ms" in body

    @pytest.mark.asyncio
    async def test_retrieve_passes_top_k(
        self, client, mock_embedding_client, mock_vector_store
    ):
        """POST /v1/retrieve passes top_k to the vector store."""
        async with client as c:
            await c.post(
                "/v1/retrieve",
                json={"corpus_id": "test-corpus", "query": "scope", "top_k": 3},
            )
        call_kwargs = mock_vector_store.search_hybrid.call_args.kwargs
        assert call_kwargs["top_k"] == 3

    @pytest.mark.asyncio
    async def test_retrieve_passes_alpha(
        self, client, mock_embedding_client, mock_vector_store
    ):
        """POST /v1/retrieve passes alpha to the vector store."""
        async with client as c:
            await c.post(
                "/v1/retrieve",
                json={"corpus_id": "test-corpus", "query": "scope", "alpha": 0.5},
            )
        call_kwargs = mock_vector_store.search_hybrid.call_args.kwargs
        assert call_kwargs["alpha"] == 0.5

    @pytest.mark.asyncio
    async def test_retrieve_embedding_error_returns_500(
        self, client, mock_embedding_client, mock_vector_store
    ):
        """POST /v1/retrieve returns 500 when embedding service fails."""
        mock_embedding_client.embed.side_effect = Exception("embedding timeout")
        async with client as c:
            response = await c.post(
                "/v1/retrieve",
                json={"corpus_id": "test-corpus", "query": "scope"},
            )
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_retrieve_vector_store_error_returns_404(
        self, client, mock_embedding_client, mock_vector_store
    ):
        """POST /v1/retrieve returns 404 when corpus is not found."""
        mock_vector_store.search_hybrid.side_effect = Exception("collection not found")
        async with client as c:
            response = await c.post(
                "/v1/retrieve",
                json={"corpus_id": "nonexistent", "query": "scope"},
            )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_retrieve_top_k_validation(self, client):
        """POST /v1/retrieve rejects top_k outside valid range."""
        async with client as c:
            response = await c.post(
                "/v1/retrieve",
                json={"corpus_id": "test-corpus", "query": "scope", "top_k": 0},
            )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_retrieve_alpha_validation(self, client):
        """POST /v1/retrieve rejects alpha outside 0.0–1.0 range."""
        async with client as c:
            response = await c.post(
                "/v1/retrieve",
                json={"corpus_id": "test-corpus", "query": "scope", "alpha": 1.5},
            )
        assert response.status_code == 422
