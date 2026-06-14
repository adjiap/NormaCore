"""Base types for the ingestion reader layer.

Defines the normalised intermediate representation (IR) that all format-specific
readers must produce. The chunker and ingestion pipeline consume only this type,
remaining format-agnostic.
"""

from dataclasses import dataclass, field


@dataclass
class DocumentSection:
    """Normalised intermediate representation of a single document section.

    All format-specific readers (Markdown, PDF, DOCX) must produce this type.
    The chunker consumes it without knowledge of the source format.

    Attributes:
        section_id: Clause identifier, either extracted from heading text or
            generated positionally.
        heading_path: Ordered list of ancestor heading texts including this
            heading, from root to current level.
        heading_level: Source heading depth (1 = top level).
        text: Body text of the section, excluding the heading line itself.
        metadata: Arbitrary key/value pairs set by the caller (source file,
            corpus_id, etc.).
    """

    section_id: str
    heading_path: list[str]
    heading_level: int
    text: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialise to a plain dict for downstream consumers.

        Returns:
            Dict with section_id, heading_path, heading_level, text,
            and metadata keys.
        """
        return {
            "section_id": self.section_id,
            "heading_path": self.heading_path,
            "heading_level": self.heading_level,
            "text": self.text,
            "metadata": self.metadata,
        }
