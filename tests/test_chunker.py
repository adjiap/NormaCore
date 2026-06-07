"""Unit tests for the structure-aware chunker."""

from pathlib import Path

import pytest

from normacore.chunker import Chunk, Chunker
from normacore.markdown_reader import MarkdownReader

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def chunker() -> Chunker:
    """Provide a Chunker with default settings."""
    return Chunker()


@pytest.fixture
def reader() -> MarkdownReader:
    """Provide a MarkdownReader instance."""
    return MarkdownReader()


@pytest.fixture
def sample_chunks(chunker, reader) -> list[Chunk]:
    """Chunk the sample standard fixture."""
    sections = reader.read(FIXTURES / "sample_standard.md")
    return chunker.chunk(sections)


@pytest.fixture
def edge_chunks(chunker, reader) -> list[Chunk]:
    """Chunk the edge cases fixture."""
    sections = reader.read(FIXTURES / "sample_edge_cases.md")
    return chunker.chunk(sections)


class TestIsGlossary:

    def test_is_glossary_detects_entry(self, chunker):
        """Single-entry glossary pattern is detected."""
        assert chunker._is_glossary("**safety goal**: top-level safety requirement.")

    def test_is_glossary_rejects_normal_text(self, chunker):
        """Normal section body is not detected as glossary."""
        assert not chunker._is_glossary("This section specifies the requirements.")

    def test_is_glossary_ignores_leading_whitespace(self, chunker):
        """Leading whitespace does not break glossary detection."""
        assert chunker._is_glossary("  **item**: system or combination of systems.")


class TestSplitRecursive:
    def test_split_recursive_produces_multiple_chunks(self, chunker, reader):
        """Oversized section produces more than one chunk."""
        sections = reader.read(FIXTURES / "sample_edge_cases.md")
        oversized = next(s for s in sections if s.section_id == "1")
        chunks = chunker._split_recursive(oversized.text, oversized, start_index=0)
        assert len(chunks) > 1

    def test_split_recursive_chunk_indices_sequential(self, chunker, reader):
        """Chunk indices are sequential starting from start_index."""
        sections = reader.read(FIXTURES / "sample_edge_cases.md")
        oversized = next(s for s in sections if s.section_id == "1")
        chunks = chunker._split_recursive(oversized.text, oversized, start_index=5)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == 5 + i

    def test_split_recursive_metadata_preserved(self, chunker, reader):
        """Source section metadata is preserved in all split chunks."""
        sections = reader.read(
            FIXTURES / "sample_edge_cases.md",
            metadata={"corpus_id": "test"},
        )
        oversized = next(s for s in sections if s.section_id == "1")
        chunks = chunker._split_recursive(oversized.text, oversized, start_index=0)
        for chunk in chunks:
            assert chunk.metadata["corpus_id"] == "test"


class TestChunk:

    def test_chunk_returns_chunks(self, sample_chunks):
        """chunk() returns a non-empty list of Chunk objects."""
        assert len(sample_chunks) > 0
        assert all(isinstance(c, Chunk) for c in sample_chunks)

    def test_chunk_indices_are_unique_and_sequential(self, sample_chunks):
        """All chunk indices are unique and sequential from 0."""
        indices = [c.chunk_index for c in sample_chunks]
        assert indices == list(range(len(sample_chunks)))

    def test_chunk_heading_path_in_text(self, sample_chunks):
        """Each chunk text is prefixed with the heading path."""
        for chunk in sample_chunks:
            assert chunk.heading_path[-1] in chunk.text

    def test_chunk_glossary_kept_atomic(self, edge_chunks):
        """Glossary entries produce exactly one chunk each."""
        glossary_chunks = [
            c
            for c in edge_chunks
            if "**functional safety**" in c.text or "**item**" in c.text
        ]
        assert len(glossary_chunks) >= 2
        for chunk in glossary_chunks:
            assert "**" in chunk.text

    def test_chunk_oversized_section_split(self, edge_chunks):
        """Oversized section produces more than one chunk."""
        oversized = [c for c in edge_chunks if c.section_id == "1"]
        assert len(oversized) > 1

    def test_chunk_empty_section_skipped(self, chunker):
        """Sections with empty body text produce no chunks."""
        from normacore.markdown_reader import MarkdownSection

        sections = [
            MarkdownSection(
                section_id="1",
                heading_path=["1 Empty"],
                heading_level=1,
                text="",
                metadata={},
            )
        ]
        chunks = chunker.chunk(sections)
        assert len(chunks) == 0

    def test_chunk_section_ids_preserved(self, sample_chunks):
        """section_id from the source section is preserved in chunks."""
        ids = [c.section_id for c in sample_chunks]
        assert "1" in ids
        assert "1.1" in ids
