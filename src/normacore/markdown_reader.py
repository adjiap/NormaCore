"""Markdown document reader producing a normalised intermediate representation.

Supports the following heading/clause numbering patterns found in technical
standards (Pareto-80 coverage):

- Pattern A — ISO/IEC dotted numeric (e.g. 1, 1.1, 1.1.1): ISO 26262,
  IEC 61508, ISO 9001, ISO/IEC 27001
- Pattern B — Flat numeric with inline clause numbers (e.g. 3.1, 3.2):
  older IEEE standards, DIN, BS, NF, and similar national bodies
- Pattern C — NIST SP alphanumeric with lettered appendices (e.g. A, A.1):
  NIST SP 800-53, SP 800-171
- Pattern D — Unnumbered prose headings (no clause numbers): MISRA C,
  AUTOSAR specs, internal company standards

For patterns A-C, section_id is extracted from the heading text via regex.
For pattern D, section_id is generated positionally from heading depth and
sibling index (e.g. "2.3.1").
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# Matches dotted numeric prefixes: "1", "1.1", "1.1.1", "A", "A.1"
_SECTION_ID_RE = re.compile(r"^(\d+(\.\d+)*|[A-Z](\.\d+)*)\s")


@dataclass
class MarkdownSection:
    """Normalised intermediate representation of a single document section.

    Attributes:
        section_id: Clause identifier, either extracted from heading text
            (patterns A-C) or generated positionally (pattern D).
        heading_path: Ordered list of ancestor heading texts including this
            heading, from root to current level.
        heading_level: Markdown heading depth (1 = #, 2 = ##, etc.).
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


class MarkdownReader:
    """Parses a Markdown file into a list of MarkdownSection objects.

    Heading detection uses ATX-style headers only (# through ######).
    Setext-style headers (underline with === or ---) are not supported.

    Section IDs are extracted from heading text when a dotted numeric or
    alphanumeric prefix is present (patterns A-C). When absent (pattern D),
    IDs are generated positionally using a depth-aware counter.
    """

    def _extract_section_id(self, heading_text: str) -> str | None:
        """Extract a clause identifier from heading text if present.

        Handles patterns A-C (ISO/IEC dotted numeric, flat numeric with
        inline clause numbers, NIST alphanumeric with lettered appendices).
        Returns None for pattern D (unnumbered prose headings), which triggers
        positional ID generation in the caller.

        Args:
            heading_text: Raw heading text with the leading # stripped.

        Returns:
            Extracted section_id string, or None if no numeric prefix found.
        """
        match = _SECTION_ID_RE.match(heading_text.strip())
        if match:
            return match.group(1)
        return None

    def _generate_section_id(self, counters: list[int], level: int) -> str:
        """Generate a positional section_id for unnumbered headings (pattern D).

        Maintains a per-level counter list. Increments the counter at the
        current level and resets all deeper counters to zero.

        Args:
            counters: Mutable list of per-level counters (modified in place).
            level: Current heading depth (1-based).

        Returns:
            Dotted string ID, e.g. "2.3.1".
        """
        # Extend counters list if this level hasn't been seen yet
        while len(counters) < level:
            counters.append(0)

        # Increment current level, reset all deeper levels
        counters[level - 1] += 1
        del counters[level:]

        return ".".join(str(c) for c in counters[:level])

    def read(self, path: Path, metadata: dict | None = None) -> list[MarkdownSection]:
        """Parse a Markdown file and return a list of sections.

        Args:
            path: Path to the .md file to parse.
            metadata: Optional key/value pairs to attach to every section
                (e.g. corpus_id, source name).

        Returns:
            Ordered list of MarkdownSection objects, one per heading.

        Raises:
            FileNotFoundError: If path does not exist.
            ValueError: If path is not a .md file.
        """
        if not path.exists():
            raise FileNotFoundError("Markdown file not found: %s" % path)
        if path.suffix != ".md":
            raise ValueError("Expected a .md file, got: %s" % path.suffix)

        logger.info("Reading markdown file: %s", path)

        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines()

        sections: list[MarkdownSection] = []
        heading_stack: list[str] = []  # tracks heading path up to current level
        counters: list[int] = []  # positional counters for pattern D
        current_heading: str | None = None
        current_level: int = 0
        current_lines: list[str] = []

        def flush(heading: str, level: int, body_lines: list[str]) -> None:
            """Finalise the current section and append it to sections."""
            text = "\n".join(body_lines).strip()
            if not text and not heading:
                return

            section_id = self._extract_section_id(heading)
            if section_id is None:
                section_id = self._generate_section_id(counters, level)

            # Trim stack to current level and update
            del heading_stack[level - 1 :]
            heading_stack.append(heading.strip())

            sections.append(
                MarkdownSection(
                    section_id=section_id,
                    heading_path=list(heading_stack),
                    heading_level=level,
                    text=text,
                    metadata=metadata or {},
                )
            )

        for line in lines:
            heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
            if heading_match:
                if current_heading is not None:
                    flush(current_heading, current_level, current_lines)
                current_level = len(heading_match.group(1))
                current_heading = heading_match.group(2)
                current_lines = []
            else:
                current_lines.append(line)

        # Flush the final section
        if current_heading is not None:
            flush(current_heading, current_level, current_lines)

        logger.info("Parsed %s sections from %s", len(sections), path)
        return sections
