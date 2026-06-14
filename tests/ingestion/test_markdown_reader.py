"""Unit tests for the Markdown reader."""

from pathlib import Path

import pytest

from normacore.ingestion.readers.markdown_reader import MarkdownReader, MarkdownSection

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture()
def reader() -> MarkdownReader:
    """Provide a MarkdownReader instance."""
    return MarkdownReader()


@pytest.fixture
def sample_sections(reader) -> list[MarkdownSection]:
    """Parse the sample standard fixture."""
    return reader.read(FIXTURES / "sample_standard.md")


class TestExtractSectionID:
    def test_extract_section_id_iso_pattern(self, reader):
        """Pattern A — ISO/IEC dotted numeric."""
        assert reader._extract_section_id("1.2.1 Inclusions") == "1.2.1"

    def test_extract_section_id_flat_numeric(self, reader):
        """Pattern B — flat numeric with inline clause number."""
        assert reader._extract_section_id("3.1 General Requirements") == "3.1"

    def test_extract_section_id_nist_appendix(self, reader):
        """Pattern C — NIST alphanumeric appendix."""
        assert reader._extract_section_id("A.1 Normative References") == "A.1"

    def test_extract_section_id_unnumbered(self, reader):
        """Pattern D — unnumbered prose heading returns None."""
        assert reader._extract_section_id("Introduction") is None

    def test_extract_section_id_top_level(self, reader):
        """Single digit top-level clause."""
        assert reader._extract_section_id("1 Scope") == "1"


class TestGenerateSectionID:
    def test_generate_section_id_sequential(self, reader):
        """Sequential top-level headings increment correctly."""
        counters: list[int] = []
        assert reader._generate_section_id(counters, 1) == "1"
        assert reader._generate_section_id(counters, 1) == "2"
        assert reader._generate_section_id(counters, 1) == "3"

    def test_generate_section_id_nested(self, reader):
        """Nested headings produce dotted IDs."""
        counters: list[int] = []
        reader._generate_section_id(counters, 1)  # 1
        assert reader._generate_section_id(counters, 2) == "1.1"
        assert reader._generate_section_id(counters, 2) == "1.2"
        assert reader._generate_section_id(counters, 3) == "1.2.1"

    def test_generate_section_id_resets_deeper_levels(self, reader):
        """Moving to a shallower level resets deeper counters."""
        counters: list[int] = []
        reader._generate_section_id(counters, 1)  # 1
        reader._generate_section_id(counters, 2)  # 1.1
        reader._generate_section_id(counters, 3)  # 1.1.1
        assert reader._generate_section_id(counters, 2) == "1.2"
        assert reader._generate_section_id(counters, 3) == "1.2.1"


class TestRead:
    def test_read_returns_sections(self, sample_sections):
        """read() returns a non-empty list of MarkdownSection objects."""
        assert len(sample_sections) > 0
        assert all(isinstance(s, MarkdownSection) for s in sample_sections)

    def test_read_section_ids_extracted(self, sample_sections):
        """Sections with numeric prefixes have extracted section_ids."""
        ids = [s.section_id for s in sample_sections]
        assert "1" in ids
        assert "1.1" in ids
        assert "1.2.1" in ids
        assert "3.1" in ids
        assert "A.1" in ids

    def test_read_heading_path_propagated(self, sample_sections):
        """Nested sections carry the full ancestor heading path."""
        section_1_2_1 = next(s for s in sample_sections if s.section_id == "1.2.1")
        assert len(section_1_2_1.heading_path) == 3
        assert "1.2.1 Inclusions" in section_1_2_1.heading_path[-1]

    def test_read_unnumbered_heading_gets_positional_id(self, sample_sections):
        """Pattern D headings receive a positional section_id."""
        intro = next(s for s in sample_sections if "Introduction" in s.heading_path[-1])
        assert intro.section_id is not None
        assert "." in intro.section_id or intro.section_id.isdigit()

    def test_read_section_text_populated(self, sample_sections):
        """Section body text is non-empty for sections with content."""
        scope = next(s for s in sample_sections if s.section_id == "1")
        assert len(scope.text) > 0

    def test_read_file_not_found(self, reader):
        """read() raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            reader.read(Path("nonexistent.md"))

    def test_read_wrong_extension(self, reader, tmp_path):
        """read() raises ValueError for non-.md files."""
        f = tmp_path / "doc.txt"
        f.write_text("hello")
        with pytest.raises(ValueError):
            reader.read(f)

    def test_read_metadata_attached(self, reader):
        """Metadata passed to read() is attached to every section."""
        sections = reader.read(
            FIXTURES / "sample_standard.md",
            metadata={"corpus_id": "test", "source": "sample"},
        )
        for section in sections:
            assert section.metadata["corpus_id"] == "test"
            assert section.metadata["source"] == "sample"
