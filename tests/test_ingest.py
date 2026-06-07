"""Unit tests for the ingestion module."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from normacore.ingest import ingest_corpus, load_manifest


@pytest.fixture
def manifest_dir(tmp_path: Path) -> Path:
    """Create a temporary corpus directory with manifest and source files."""
    standard = tmp_path / "standard.md"
    standard.write_text(
        "# 1 Scope\n\nThis document specifies requirements.\n\n"
        "## 1.1 Purpose\n\nThe purpose is to provide guidance.\n"
    )

    manifest = tmp_path / "corpus.yaml"
    manifest.write_text(
        "corpus_id: test-corpus\n"
        "description: Test corpus\n"
        "sources:\n"
        "  - name: standard\n"
        "    path: ./standard.md\n"
        "    type: markdown\n"
    )

    return tmp_path


class TestLoadManifest:

    def test_load_manifest_happy_path(self, manifest_dir):
        """load_manifest() returns parsed manifest dict."""
        manifest = load_manifest(manifest_dir / "corpus.yaml")
        assert manifest["corpus_id"] == "test-corpus"
        assert len(manifest["sources"]) == 1

    def test_load_manifest_file_not_found(self, tmp_path):
        """load_manifest() raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_manifest(tmp_path / "nonexistent.yaml")

    def test_load_manifest_missing_required_fields(self, tmp_path):
        """load_manifest() raises ValueError for missing required fields."""
        manifest = tmp_path / "corpus.yaml"
        manifest.write_text("description: Missing corpus_id and sources\n")
        with pytest.raises(ValueError):
            load_manifest(manifest)

    def test_load_manifest_missing_sources(self, tmp_path):
        """load_manifest() raises ValueError when sources field is absent."""
        manifest = tmp_path / "corpus.yaml"
        manifest.write_text("corpus_id: test-corpus\n")
        with pytest.raises(ValueError):
            load_manifest(manifest)


class TestIngestCorpus:

    @pytest.fixture
    def mock_vector_store(self):
        """Provide a mocked QdrantVectorStore."""
        with patch("normacore.ingest.QdrantVectorStore") as mock:
            instance = AsyncMock()
            mock.return_value = instance
            yield instance

    @pytest.fixture
    def mock_embedding_client(self):
        """Provide a mocked EmbeddingClient."""
        with patch("normacore.ingest.EmbeddingClient") as mock:
            instance = AsyncMock()
            instance.embed.return_value = [[0.1] * 1024]
            mock.return_value = instance
            yield instance

    @pytest.mark.asyncio
    async def test_ingest_corpus_happy_path(
        self, manifest_dir, mock_vector_store, mock_embedding_client
    ):
        """ingest_corpus() creates collection and upserts chunks."""
        await ingest_corpus(manifest_dir / "corpus.yaml", "test-corpus")

        mock_vector_store.create_collection.assert_called_once_with("test-corpus")
        mock_vector_store.upsert_chunks.assert_called_once()
        call_args = mock_vector_store.upsert_chunks.call_args
        assert call_args.args[0] == "test-corpus"
        assert len(call_args.args[1]) > 0

    @pytest.mark.asyncio
    async def test_ingest_corpus_wrong_corpus_id(
        self, manifest_dir, mock_vector_store, mock_embedding_client
    ):
        """ingest_corpus() raises ValueError for mismatched corpus_id."""
        with pytest.raises(ValueError):
            await ingest_corpus(manifest_dir / "corpus.yaml", "wrong-corpus")

    @pytest.mark.asyncio
    async def test_ingest_corpus_unsupported_source_type(
        self, manifest_dir, mock_vector_store, mock_embedding_client
    ):
        """Unsupported source types are skipped without raising."""
        manifest = manifest_dir / "corpus.yaml"
        manifest.write_text(
            "corpus_id: test-corpus\n"
            "description: Test corpus\n"
            "sources:\n"
            "  - name: standard\n"
            "    path: ./standard.md\n"
            "    type: pdf\n"
        )
        await ingest_corpus(manifest, "test-corpus")
        mock_vector_store.upsert_chunks.assert_not_called()

    @pytest.mark.asyncio
    async def test_ingest_corpus_embeds_all_chunks_in_batch(
        self, manifest_dir, mock_vector_store, mock_embedding_client
    ):
        """embed() is called once per source with all chunk texts."""
        mock_embedding_client.embed.return_value = [[0.1] * 1024] * 10

        await ingest_corpus(manifest_dir / "corpus.yaml", "test-corpus")

        assert mock_embedding_client.embed.call_count == 1
        call_args = mock_embedding_client.embed.call_args
        assert isinstance(call_args.args[0], list)
        assert all(isinstance(t, str) for t in call_args.args[0])
