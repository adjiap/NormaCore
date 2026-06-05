"""Unit tests for the vector store interface and Qdrant implementation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from normacore.vector_store import QdrantVectorStore


@pytest.fixture
def mock_qdrant_client():
    """Provide a mocked AsyncQdrantClient."""
    with patch("normacore.vector_store.AsyncQdrantClient") as mock:
        mock.return_value = AsyncMock()
        yield mock.return_value


@pytest.fixture
def store(mock_qdrant_client):
    """Provide a QdrantVectorStore with a mocked client."""
    return QdrantVectorStore()


@pytest.mark.asyncio
async def test_create_collection(store, mock_qdrant_client):
    """Test collection creation on a clean instance."""
    mock_qdrant_client.get_collections.return_value = MagicMock(collections=[])

    await store.create_collection("test-corpus")

    mock_qdrant_client.create_collection.assert_called_once()
    call_kwargs = mock_qdrant_client.create_collection.call_args.kwargs
    assert call_kwargs["collection_name"] == "test-corpus"
    assert "dense" in call_kwargs["vectors_config"]
    assert "sparse" in call_kwargs["sparse_vectors_config"]


@pytest.mark.asyncio
async def test_create_collection_existing(store, mock_qdrant_client):
    """Test that an existing collection is deleted before recreation."""
    existing = MagicMock()
    existing.name = "test-corpus"
    mock_qdrant_client.get_collections.return_value = MagicMock(collections=[existing])

    await store.create_collection("test-corpus")

    mock_qdrant_client.delete_collection.assert_called_once_with("test-corpus")
    mock_qdrant_client.create_collection.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_chunks(store, mock_qdrant_client):
    """Test that chunks are upserted with correct structure."""
    chunks = [
        {
            "chunk_index": i,
            "text": f"chunk text {i}",
            "dense_vector": [0.1] * 1024,
            "sparse_indices": [0, 1, 2],
            "sparse_values": [0.5, 0.3, 0.2],
            "metadata": {
                "section_id": f"1.{i}",
                "heading_path": ["Introduction"],
            },
        }
        for i in range(5)
    ]

    await store.upsert_chunks("test-corpus", chunks)

    mock_qdrant_client.upsert.assert_called_once()
    call_kwargs = mock_qdrant_client.upsert.call_args.kwargs
    assert call_kwargs["collection_name"] == "test-corpus"
    assert len(call_kwargs["points"]) == 5


@pytest.mark.asyncio
async def test_search_hybrid(store, mock_qdrant_client):
    """Test that hybrid search returns correctly formatted chunks."""
    mock_point = MagicMock()
    mock_point.score = 0.9
    mock_point.payload = {
        "text": "relevant chunk",
        "corpus_id": "test-corpus",
        "section_id": "1.1",
        "heading_path": ["Introduction"],
    }
    mock_qdrant_client.query_points.return_value = MagicMock(points=[mock_point])

    results = await store.search_hybrid(
        corpus_id="test-corpus",
        query_vector=[0.1] * 1024,
        query_text="test query",
        top_k=5,
    )

    assert len(results) == 1
    assert results[0]["text"] == "relevant chunk"
    assert results[0]["score"] == 0.9
    assert "corpus_id" in results[0]["metadata"]
    mock_qdrant_client.query_points.assert_called_once()


@pytest.mark.asyncio
async def test_delete_collection(store, mock_qdrant_client):
    """Test that delete_collection calls the client with the correct corpus_id."""
    await store.delete_collection("test-corpus")

    mock_qdrant_client.delete_collection.assert_called_once_with("test-corpus")
