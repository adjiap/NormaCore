"""Retrieval quality evaluation metrics for NormaCore corpora.

Computes Recall@k and MRR (Mean Reciprocal Rank) against a set of
query fixtures, each specifying expected chunk identifiers and their
maximum acceptable rank.

Default quality thresholds:
    Recall@5 >= 0.85
    MRR      >= 0.70

Usage:
    python -m normacore.eval --corpus-id <id> --fixtures <path>

Or via Makefile:
    make eval CORPUS=<id>
"""

import argparse
import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from normacore.config import settings
from normacore.logging import configure_logging
from normacore.retrieval.embedding import EmbeddingClient
from normacore.retrieval.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)

DEFAULT_RECALL_THRESHOLD = 0.85
DEFAULT_MRR_THRESHOLD = 0.70
DEFAULT_K = 5


@dataclass
class EvalFixture:
    """A single evaluation query with expected results.

    Attributes:
        query: The query string to retrieve against.
        expected_chunks: List of dicts with chunk_id and min_rank keys.
    """

    query: str
    expected_chunks: list[dict] = field(default_factory=list)


@dataclass
class EvalResult:
    """Evaluation result for a single query fixture.

    Attributes:
        query: The query string evaluated.
        hits: Number of expected chunks found in top-k results.
        expected: Total number of expected chunks.
        reciprocal_rank: 1/rank of the first relevant result, or 0.0.
    """

    query: str
    hits: int
    expected: int
    reciprocal_rank: float

    @property
    def recall(self) -> float:
        """Fraction of expected chunks found in top-k results."""
        if self.expected == 0:
            return 1.0
        return self.hits / self.expected


@dataclass
class EvalReport:
    """Aggregated evaluation report across all fixtures.

    Attributes:
        corpus_id: The corpus evaluated.
        k: The top-k cutoff used.
        results: Per-query EvalResult objects.
        recall_threshold: Minimum acceptable Recall@k.
        mrr_threshold: Minimum acceptable MRR.
    """

    corpus_id: str
    k: int
    results: list[EvalResult] = field(default_factory=list)
    recall_threshold: float = DEFAULT_RECALL_THRESHOLD
    mrr_threshold: float = DEFAULT_MRR_THRESHOLD

    @property
    def recall_at_k(self) -> float:
        """Mean Recall@k across all query fixtures."""
        if not self.results:
            return 0.0
        return sum(r.recall for r in self.results) / len(self.results)

    @property
    def mrr(self) -> float:
        """Mean Reciprocal Rank across all query fixtures."""
        if not self.results:
            return 0.0
        return sum(r.reciprocal_rank for r in self.results) / len(self.results)

    @property
    def passed(self) -> bool:
        """True if both Recall@k and MRR meet their thresholds."""
        return (
            self.recall_at_k >= self.recall_threshold and self.mrr >= self.mrr_threshold
        )

    def summary(self) -> str:
        """Format a human-readable summary of the evaluation report.

        Returns:
            Multi-line string with metrics table and pass/fail verdict.
        """
        lines = [
            f"Evaluation report — corpus: {self.corpus_id}",
            f"{'─' * 50}",
            f"Queries evaluated : {len(self.results)}",
            f"Recall@{self.k}          : {self.recall_at_k:.3f} "
            f"(threshold: {self.recall_threshold:.2f})",
            f"MRR               : {self.mrr:.3f} "
            f"(threshold: {self.mrr_threshold:.2f})",
            f"{'─' * 50}",
            f"Result            : {'PASS ✓' if self.passed else 'FAIL ✗'}",
        ]
        return "\n".join(lines)


def load_fixtures(fixtures_path: Path) -> list[EvalFixture]:
    """Load evaluation fixtures from a YAML file.

    Expected format:
        - query: "What is the definition of risk?"
          expected_chunks:
            - chunk_id: "glossary:risk"
              min_rank: 1

    Args:
        fixtures_path: Path to the fixtures YAML file.

    Returns:
        List of EvalFixture objects.

    Raises:
        FileNotFoundError: If the fixtures file does not exist.
    """
    if not fixtures_path.exists():
        raise FileNotFoundError("Fixtures file not found: %s" % fixtures_path)

    with fixtures_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    fixtures = []
    for item in raw:
        fixtures.append(
            EvalFixture(
                query=item["query"],
                expected_chunks=item.get("expected_chunks", []),
            )
        )

    logger.info("Loaded %s eval fixtures from %s", len(fixtures), fixtures_path)
    return fixtures


def compute_reciprocal_rank(
    results: list[dict],
    expected_chunks: list[dict],
) -> float:
    """Compute the reciprocal rank of the first relevant result.

    Args:
        results: Ranked list of chunk dicts returned by hybrid search.
        expected_chunks: List of dicts with chunk_id and min_rank keys.

    Returns:
        1/rank of the first relevant result, or 0.0 if none found.
    """
    for rank, result in enumerate(results, start=1):
        section_id = result.get("metadata", {}).get("section_id", "")
        for expected in expected_chunks:
            if expected["chunk_id"] == section_id and rank <= expected.get(
                "min_rank", 5
            ):
                return 1.0 / rank
    return 0.0


def compute_recall(
    results: list[dict],
    expected_chunks: list[dict],
    k: int,
) -> int:
    """Count how many expected chunks appear in the top-k results.

    Args:
        results: Ranked list of chunk dicts returned by hybrid search.
        expected_chunks: List of dicts with chunk_id and min_rank keys.
        k: Top-k cutoff.

    Returns:
        Number of expected chunks found in top-k results.
    """
    top_k = results[:k]
    section_ids = {r.get("metadata", {}).get("section_id", "") for r in top_k}
    hits = sum(1 for e in expected_chunks if e["chunk_id"] in section_ids)
    return hits


async def evaluate_corpus(
    corpus_id: str,
    fixtures: list[EvalFixture],
    k: int = DEFAULT_K,
    recall_threshold: float = DEFAULT_RECALL_THRESHOLD,
    mrr_threshold: float = DEFAULT_MRR_THRESHOLD,
) -> EvalReport:
    """Run evaluation against a corpus using the provided fixtures.

    For each fixture, embeds the query, runs hybrid search, and computes
    Recall@k and MRR against expected chunks.

    Args:
        corpus_id: Target corpus to evaluate.
        fixtures: List of EvalFixture objects with queries and expected chunks.
        k: Top-k cutoff for retrieval. Defaults to 5.
        recall_threshold: Minimum acceptable Recall@k. Defaults to 0.85.
        mrr_threshold: Minimum acceptable MRR. Defaults to 0.70.

    Returns:
        EvalReport with per-query results and aggregated metrics.
    """
    embedding_client = EmbeddingClient()
    vector_store = QdrantVectorStore()

    report = EvalReport(
        corpus_id=corpus_id,
        k=k,
        recall_threshold=recall_threshold,
        mrr_threshold=mrr_threshold,
    )

    logger.info(
        "Evaluating corpus '%s' with %s fixtures (k=%s)",
        corpus_id,
        len(fixtures),
        k,
    )

    for fixture in fixtures:
        vectors = await embedding_client.embed(fixture.query)
        query_vector = vectors[0]

        results = await vector_store.search_hybrid(
            corpus_id=corpus_id,
            query_vector=query_vector,
            query_text=fixture.query,
            top_k=k,
        )

        hits = compute_recall(results, fixture.expected_chunks, k)
        rr = compute_reciprocal_rank(results, fixture.expected_chunks)

        report.results.append(
            EvalResult(
                query=fixture.query,
                hits=hits,
                expected=len(fixture.expected_chunks),
                reciprocal_rank=rr,
            )
        )

        logger.debug(
            "Query '%s' — hits: %s/%s, RR: %.3f",
            fixture.query,
            hits,
            len(fixture.expected_chunks),
            rr,
        )

    logger.info(
        "Evaluation complete — Recall@%s: %.3f, MRR: %.3f, %s",
        k,
        report.recall_at_k,
        report.mrr,
        "PASS" if report.passed else "FAIL",
    )

    return report


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace with corpus_id and fixtures.
    """
    parser = argparse.ArgumentParser(
        description="Run retrieval quality evaluation for a NormaCore corpus."
    )
    parser.add_argument(
        "--corpus-id",
        type=str,
        required=True,
        help="Corpus identifier to evaluate.",
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        required=True,
        help="Path to the eval fixtures YAML file.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=DEFAULT_K,
        help="Top-k cutoff for retrieval (default: 5).",
    )
    parser.add_argument(
        "--recall-threshold",
        type=float,
        default=DEFAULT_RECALL_THRESHOLD,
        help="Minimum acceptable Recall@k (default: 0.85).",
    )
    parser.add_argument(
        "--mrr-threshold",
        type=float,
        default=DEFAULT_MRR_THRESHOLD,
        help="Minimum acceptable MRR (default: 0.70).",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for the evaluation script."""
    configure_logging(settings.log_file, settings.log_level)
    args = parse_args()

    fixtures = load_fixtures(args.fixtures)
    report = asyncio.run(
        evaluate_corpus(
            corpus_id=args.corpus_id,
            fixtures=fixtures,
            k=args.k,
            recall_threshold=args.recall_threshold,
            mrr_threshold=args.mrr_threshold,
        )
    )

    print(report.summary())
    raise SystemExit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
