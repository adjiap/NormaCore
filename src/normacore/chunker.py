"""Structure-aware chunker for technical document sections.

Chunking strategies applied in order:

1. Structure-aware split — one chunk per MarkdownSection (happy path).
   Heading path is carried into each chunk as contextual metadata.
2. Recursive fallback — if a section body exceeds the token limit, split
   on paragraph boundaries (\\n\\n), then sentence boundaries. Overlap of
   10-20% is applied between sibling chunks to preserve context.
3. Glossary detection — sections matching the single-entry glossary pattern
   (\"**term**: definition\") are kept atomic and never split.
"""

import logging
import re
from dataclasses import dataclass, field

from normacore.markdown_reader import MarkdownSection

logger = logging.getLogger(__name__)

# Default token limit per chunk (approximate — 1 token ≈ 4 chars)
_DEFAULT_MAX_TOKENS = 512
_CHARS_PER_TOKEN = 4

# Glossary entry pattern: **term**: definition
_GLOSSARY_RE = re.compile(r"^\*\*[^*]+\*\*\s*:")


@dataclass
class Chunk:
    """A single text unit ready for embedding and upsert.

    Attributes:
        text: The chunk body, prefixed with heading path for context.
        section_id: Clause identifier from the source section.
        heading_path: Ancestor heading list from the source section.
        chunk_index: Zero-based index of this chunk within the corpus.
        metadata: Arbitrary key/value pairs inherited from the source section.
    """

    text: str
    section_id: str
    heading_path: list[str]
    chunk_index: int
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialise to a plain dict for downstream consumers.

        Returns:
            Dict with text, section_id, heading_path, chunk_index,
            and metadata keys.
        """
        return {
            "text": self.text,
            "section_id": self.section_id,
            "heading_path": self.heading_path,
            "chunk_index": self.chunk_index,
            "metadata": self.metadata,
        }


class Chunker:
    """Converts a list of MarkdownSection objects into embeddable chunks.

    Args:
        max_tokens: Maximum tokens per chunk before recursive fallback
            is triggered. Defaults to 512.
        overlap: Fractional overlap between sibling chunks produced by
            recursive fallback. Must be between 0.0 and 0.5.
    """

    def __init__(
        self,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        overlap: float = 0.15,
    ) -> None:
        self._max_chars = max_tokens * _CHARS_PER_TOKEN
        self._overlap = overlap

    def _chunk_section(
        self,
        section: MarkdownSection,
        start_index: int,
    ) -> list[Chunk]:
        """Produce one or more chunks from a single section.

        Applies glossary detection first, then size check, then recursive
        fallback if needed.

        Args:
            section: The source MarkdownSection.
            start_index: chunk_index offset for the first chunk produced.

        Returns:
            List of one or more Chunk objects.
        """
        text = section.text.strip()

        if not text:
            logger.debug("Skipping empty section %s", section.section_id)
            return []

        # Prefix text with heading path for contextual retrieval
        heading_prefix = " > ".join(section.heading_path)
        full_text = f"{heading_prefix}\n\n{text}"

        # Glossary entries are always atomic
        if self._is_glossary(text):
            logger.debug(
                "Section %s detected as glossary entry — keeping atomic",
                section.section_id,
            )
            return [
                Chunk(
                    text=full_text,
                    section_id=section.section_id,
                    heading_path=section.heading_path,
                    chunk_index=start_index,
                    metadata=section.metadata,
                )
            ]

        if len(full_text) <= self._max_chars:
            return [
                Chunk(
                    text=full_text,
                    section_id=section.section_id,
                    heading_path=section.heading_path,
                    chunk_index=start_index,
                    metadata=section.metadata,
                )
            ]

        # Recursive fallback for oversized sections
        logger.debug(
            "Section %s exceeds %s chars — triggering recursive split",
            section.section_id,
            self._max_chars,
        )
        return self._split_recursive(full_text, section, start_index)

    def _is_glossary(self, text: str) -> bool:
        """Detect single-entry glossary sections.

        A glossary entry matches the pattern **term**: definition on the
        first non-empty line of the section body.

        Args:
            text: Section body text.

        Returns:
            True if the section is a glossary entry, False otherwise.
        """
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                return bool(_GLOSSARY_RE.match(stripped))
        return False

    def _split_recursive(
        self,
        text: str,
        section: MarkdownSection,
        start_index: int,
    ) -> list[Chunk]:
        """Recursively split oversized text into overlapping chunks.

        Attempts paragraph split (\\n\\n) first. Falls back to sentence
        split if paragraphs are still too large. Applies overlap between
        sibling chunks.

        Args:
            text: The oversized text to split.
            section: Source section for metadata and heading path.
            start_index: chunk_index offset for the first chunk produced.

        Returns:
            List of Chunk objects with overlap applied.
        """
        # Try paragraph split first, then sentence split
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) == 1:
            # No paragraph boundaries — fall back to sentence split
            paragraphs = [
                s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()
            ]

        # Bin paragraphs into chunks respecting max_chars with overlap
        chunks: list[Chunk] = []
        current_parts: list[str] = []
        current_len = 0
        overlap_chars = int(self._max_chars * self._overlap)

        for part in paragraphs:
            part_len = len(part)
            if current_len + part_len > self._max_chars and current_parts:
                chunk_text = "\n\n".join(current_parts)
                chunks.append(
                    Chunk(
                        text=chunk_text,
                        section_id=section.section_id,
                        heading_path=section.heading_path,
                        chunk_index=start_index + len(chunks),
                        metadata=section.metadata,
                    )
                )
                # Carry overlap from the end of the current window
                overlap_text = chunk_text[-overlap_chars:] if overlap_chars else ""
                current_parts = [overlap_text] if overlap_text else []
                current_len = len(overlap_text)

            current_parts.append(part)
            current_len += part_len

        # Flush remaining parts
        if current_parts:
            chunks.append(
                Chunk(
                    text="\n\n".join(current_parts),
                    section_id=section.section_id,
                    heading_path=section.heading_path,
                    chunk_index=start_index + len(chunks),
                    metadata=section.metadata,
                )
            )

        logger.debug(
            "Recursive split of section %s produced %s chunks",
            section.section_id,
            len(chunks),
        )
        return chunks

    def chunk(self, sections: list[MarkdownSection]) -> list[Chunk]:
        """Convert a flat list of sections into embeddable chunks.

        Args:
            sections: Ordered list of MarkdownSection objects from the reader.

        Returns:
            Flat list of Chunk objects with index, text, and metadata.
        """
        chunks: list[Chunk] = []

        for section in sections:
            new_chunks = self._chunk_section(section, start_index=len(chunks))
            chunks.extend(new_chunks)

        logger.info("Chunked %s sections into %s chunks", len(sections), len(chunks))
        return chunks
