"""Unit tests for the evaluation metrics module."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from normacore.eval import (
    EvalFixture,
    EvalReport,
    EvalResult,
    compute_recall,
    compute_reciprocal_rank,
    evaluate_corpus,
    load_fixtures,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_results() -> list[dict]:
    """Provide a ranked list of mock retrieval results."""
    return [
        {"text": "chunk 1", "score": 0.9, "metadata": {"section_id": "1.1"}},
        {"text": "chunk 2", "score": 0.8, "metadata": {"section_id": "1.2"}},
        {"text": "chunk 3", "score": 0.7, "metadata": {"section_id": "2.1"}},
        {"text": "chunk 4", "score": 0.6, "metadata": {"section_id": "2.2"}},
        {"text": "chunk 5", "score": 0.5, "metadata": {"section_id": "3.1"}},
    ]


@pytest.fixture
def fixtures_yaml(tmp_path: Path) -> Path:
    """Write a minimal fixtures YAML file."""
    content = (
        "- query: What is the scope?\n"
        "  expected_chunks:\n"
        "    - chunk_id: '1.1'\n"
        "      min_rank: 1\n"
        "- query: What are the requirements?\n"
        "  expected_chunks:\n"
        "    - chunk_id: '2.1'\n"
        "      min_rank: 3\n"
    )
    f = tmp_path / "fixtures.yaml"
    f.write_text(content)
    return f


class TestLoadFixtures:

    def test_load_fixtures_happy_path(self, fixtures_yaml):
        """load_fixtures() returns correct number of EvalFixture objects."""
        fixtures = load_fixtures(fixtures_yaml)
        assert len(fixtures) == 2
        assert fixtures[0].query == "What is the scope?"
        assert fixtures[0].expected_chunks[0]["chunk_id"] == "1.1"

    def test_load_fixtures_file_not_found(self, tmp_path):
        """load_fixtures() raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_fixtures(tmp_path / "nonexistent.yaml")


class TestComputeRecall:

    def test_recall_all_found(self, sample_results):
        """Recall is 1.0 when all expected chunks are in top-k."""
        expected = [
            {"chunk_id": "1.1", "min_rank": 1},
            {"chunk_id": "2.1", "min_rank": 3},
        ]
        assert compute_recall(sample_results, expected, k=5) == 2

    def test_recall_partial(self, sample_results):
        """Recall counts only chunks found in top-k."""
        expected = [
            {"chunk_id": "1.1", "min_rank": 1},
            {"chunk_id": "9.9", "min_rank": 1},
        ]
        assert compute_recall(sample_results, expected, k=5) == 1

    def test_recall_none_found(self, sample_results):
        """Recall is 0 when no expected chunks are in top-k."""
        expected = [{"chunk_id": "9.9", "min_rank": 1}]
        assert compute_recall(sample_results, expected, k=5) == 0

    def test_recall_respects_k_cutoff(self, sample_results):
        """Recall only considers results within top-k."""
        expected = [{"chunk_id": "3.1", "min_rank": 5}]
        assert compute_recall(sample_results, expected, k=3) == 0
        assert compute_recall(sample_results, expected, k=5) == 1


class TestComputeReciprocalRank:

    def test_rr_first_result(self, sample_results):
        """RR is 1.0 when first result matches."""
        expected = [{"chunk_id": "1.1", "min_rank": 1}]
        assert compute_reciprocal_rank(sample_results, expected) == 1.0

    def test_rr_third_result(self, sample_results):
        """RR is 1/3 when third result matches."""
        expected = [{"chunk_id": "2.1", "min_rank": 3}]
        assert compute_reciprocal_rank(sample_results, expected) == pytest.approx(1 / 3)

    def test_rr_no_match(self, sample_results):
        """RR is 0.0 when no expected chunk is found."""
        expected = [{"chunk_id": "9.9", "min_rank": 1}]
        assert compute_reciprocal_rank(sample_results, expected) == 0.0

    def test_rr_empty_expected(self, sample_results):
        """RR is 0.0 when expected_chunks is empty."""
        assert compute_reciprocal_rank(sample_results, []) == 0.0


class TestEvalReport:

    def test_recall_at_k_computed(self):
        """recall_at_k is mean recall across results."""
        report = EvalReport(corpus_id="test", k=5)
        report.results = [
            EvalResult(query="q1", hits=1, expected=1, reciprocal_rank=1.0),
            EvalResult(query="q2", hits=0, expected=1, reciprocal_rank=0.0),
        ]
        assert report.recall_at_k == pytest.approx(0.5)

    def test_mrr_computed(self):
        """MRR is mean reciprocal rank across results."""
        report = EvalReport(corpus_id="test", k=5)
        report.results = [
            EvalResult(query="q1", hits=1, expected=1, reciprocal_rank=1.0),
            EvalResult(query="q2", hits=1, expected=1, reciprocal_rank=0.5),
        ]
        assert report.mrr == pytest.approx(0.75)

    def test_passed_when_above_thresholds(self):
        """passed is True when both metrics meet thresholds."""
        report = EvalReport(corpus_id="test", k=5)
        report.results = [
            EvalResult(query="q1", hits=1, expected=1, reciprocal_rank=1.0),
        ]
        assert report.passed is True

    def test_failed_when_below_recall_threshold(self):
        """passed is False when Recall@k is below threshold."""
        report = EvalReport(corpus_id="test", k=5, recall_threshold=0.9)
        report.results = [
            EvalResult(query="q1", hits=0, expected=1, reciprocal_rank=1.0),
        ]
        assert report.passed is False

    def test_summary_contains_metrics(self):
        """summary() output contains corpus_id, recall, and MRR."""
        report = EvalReport(corpus_id="test-corpus", k=5)
        report.results = [
            EvalResult(query="q1", hits=1, expected=1, reciprocal_rank=1.0),
        ]
        summary = report.summary()
        assert "test-corpus" in summary
        assert "Recall@5" in summary
        assert "MRR" in summary


class TestEvaluateCorpus:

    @pytest.fixture
    def mock_vector_store(self):
        """Provide a mocked QdrantVectorStore."""
        with patch("normacore.eval.QdrantVectorStore") as mock:
            instance = AsyncMock()
            instance.search_hybrid.return_value = [
                {"text": "chunk", "score": 0.9, "metadata": {"section_id": "1.1"}},
            ]
            mock.return_value = instance
            yield instance

    @pytest.fixture
    def mock_embedding_client(self):
        """Provide a mocked EmbeddingClient."""
        with patch("normacore.eval.EmbeddingClient") as mock:
            instance = AsyncMock()
            instance.embed.return_value = [[0.1] * 1024]
            mock.return_value = instance
            yield instance

    @pytest.mark.asyncio
    async def test_evaluate_corpus_returns_report(
        self, mock_vector_store, mock_embedding_client
    ):
        """evaluate_corpus() returns an EvalReport."""
        fixtures = [
            EvalFixture(
                query="What is the scope?",
                expected_chunks=[{"chunk_id": "1.1", "min_rank": 1}],
            )
        ]
        report = await evaluate_corpus("test-corpus", fixtures)
        assert isinstance(report, EvalReport)
        assert len(report.results) == 1

    @pytest.mark.asyncio
    async def test_evaluate_corpus_calls_search_per_fixture(
        self, mock_vector_store, mock_embedding_client
    ):
        """search_hybrid is called once per fixture."""
        fixtures = [
            EvalFixture(query="query 1", expected_chunks=[]),
            EvalFixture(query="query 2", expected_chunks=[]),
        ]
        await evaluate_corpus("test-corpus", fixtures)
        assert mock_vector_store.search_hybrid.call_count == 2

    @pytest.mark.asyncio
    async def test_evaluate_corpus_pass(self, mock_vector_store, mock_embedding_client):
        """evaluate_corpus() report passes when results meet thresholds."""
        fixtures = [
            EvalFixture(
                query="What is the scope?",
                expected_chunks=[{"chunk_id": "1.1", "min_rank": 1}],
            )
        ]
        report = await evaluate_corpus(
            "test-corpus",
            fixtures,
            recall_threshold=0.5,
            mrr_threshold=0.5,
        )
        assert report.passed is True
