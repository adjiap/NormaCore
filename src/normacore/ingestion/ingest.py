"""Ingestion script for NormaCore corpora.

Reads a corpus manifest (corpus.yaml), parses each source document,
chunks it, embeds all chunks in a single batched call, and upserts
into Qdrant. Re-running is idempotent — the collection is recreated
from scratch on each run.

Usage:
    python scripts/ingest.py --corpus-manifest ./corpus.yaml --corpus-id <id>

Or via Makefile:
    make ingest CORPUS=<id>
"""

import argparse
import asyncio
import logging
from pathlib import Path

import yaml

from normacore.config import settings
from normacore.ingestion.chunker import Chunker
from normacore.ingestion.readers.markdown_reader import MarkdownReader
from normacore.logging import configure_logging
from normacore.retrieval.embedding import EmbeddingClient
from normacore.retrieval.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)


def load_manifest(manifest_path: Path) -> dict:
    """Load and parse a corpus.yaml manifest file.

    Args:
        manifest_path: Path to the corpus.yaml file.

    Returns:
        Parsed manifest as a dict.

    Raises:
        FileNotFoundError: If the manifest file does not exist.
        ValueError: If the manifest is missing required fields.
    """
    if not manifest_path.exists():
        raise FileNotFoundError("Manifest not found: %s" % manifest_path)

    with manifest_path.open(encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    required = {"corpus_id", "sources"}
    missing = required - set(manifest.keys())
    if missing:
        raise ValueError("Manifest missing required fields: %s" % missing)

    return manifest


async def ingest_corpus(manifest_path: Path, corpus_id: str) -> int:
    """Ingest a corpus from a manifest file into Qdrant.

    Reads each source document, chunks it, embeds all chunks in a
    single batched call per source, and upserts into Qdrant. The
    collection is recreated from scratch on each run (idempotent).

    Args:
        manifest_path: Path to the corpus.yaml manifest file.
        corpus_id: Corpus identifier to ingest. Must match a corpus_id
            in the manifest.

    Returns:
        Total number of chunks upserted across all sources in the corpus.

    Raises:
        FileNotFoundError: If the manifest or a source file does not exist.
        ValueError: If the corpus_id is not found in the manifest.
    """
    manifest = load_manifest(manifest_path)

    if manifest["corpus_id"] != corpus_id:
        raise ValueError(
            "corpus_id '%s' not found in manifest (found '%s')"
            % (corpus_id, manifest["corpus_id"])
        )

    reader = MarkdownReader()
    chunker = Chunker()
    embedding_client = EmbeddingClient()
    vector_store = QdrantVectorStore()

    logger.info("Starting ingestion for corpus: %s", corpus_id)

    # Recreate collection from scratch (idempotent)
    await vector_store.create_collection(corpus_id)

    total_chunks = 0

    for source in manifest["sources"]:
        source_name = source["name"]
        source_path = manifest_path.parent / source["path"]
        source_type = source.get("type", "markdown")

        logger.info("Processing source: %s (%s)", source_name, source_type)

        if source_type != "markdown":
            logger.warning(
                "Source type '%s' not supported yet — skipping %s",
                source_type,
                source_name,
            )
            continue

        # Read and chunk
        sections = reader.read(
            source_path,
            metadata={"corpus_id": corpus_id, "source": source_name},
        )
        chunks = chunker.chunk(sections)

        if not chunks:
            logger.warning("No chunks produced from source: %s", source_name)
            continue

        logger.info("Produced %s chunks from source: %s", len(chunks), source_name)

        # Embed all chunks in a single batched call
        texts = [chunk.text for chunk in chunks]
        logger.info("Embedding %s chunks for source: %s", len(texts), source_name)
        dense_vectors = await embedding_client.embed(texts)

        # Build upsert payload
        upsert_chunks = []
        for chunk, dense_vector in zip(chunks, dense_vectors):
            upsert_chunks.append(
                {
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "dense_vector": dense_vector,
                    # Sparse vectors handled natively by Qdrant BM25
                    "sparse_indices": [],
                    "sparse_values": [],
                    "metadata": {
                        **chunk.metadata,
                        "section_id": chunk.section_id,
                        "heading_path": chunk.heading_path,
                    },
                }
            )

        await vector_store.upsert_chunks(corpus_id, upsert_chunks)
        total_chunks += len(upsert_chunks)
        logger.info(
            "Upserted %s chunks for source: %s", len(upsert_chunks), source_name
        )

    logger.info(
        "Ingestion complete for corpus '%s' — %s total chunks indexed",
        corpus_id,
        total_chunks,
    )
    return total_chunks


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace with corpus_manifest and corpus_id.
    """
    parser = argparse.ArgumentParser(description="Ingest a corpus into NormaCore.")
    parser.add_argument(
        "--corpus-manifest",
        type=Path,
        required=True,
        help="Path to the corpus.yaml manifest file.",
    )
    parser.add_argument(
        "--corpus-id",
        type=str,
        required=True,
        help="Corpus identifier to ingest.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for the ingestion script."""
    configure_logging(settings.log_file, settings.log_level)
    args = parse_args()
    asyncio.run(ingest_corpus(args.corpus_manifest, args.corpus_id))


if __name__ == "__main__":
    main()
