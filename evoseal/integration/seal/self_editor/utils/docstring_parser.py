"""Utilities for parsing and generating docstrings in different formats."""

import re
from enum import Enum
from typing import NamedTuple, Optional, Union


class DocstringStyle(Enum):
    """Supported docstring styles."""

    GOOGLE = "google"
    NUMPY = "numpy"
    REST = "rest"


class DocstringSection(NamedTuple):
    """Represents a section in a docstring."""

    title: str
    content: str


class ParsedDocstring:
    """Represents a parsed docstring with its components."""

    def __init__(
        self,
        summary: str = "",
        description: str = "",
        sections: Optional[dict[str, str]] = None,
        style: DocstringStyle = DocstringStyle.GOOGLE,
    ):
        self.summary = summary
        self.description = description
        self.sections = sections or {}
        self.style = style

    def to_string(self) -> str:
        """Convert the parsed docstring back to a string."""
        if self.style == DocstringStyle.GOOGLE:
            return self._to_google_docstring()
        elif self.style == DocstringStyle.NUMPY:
            return self._to_numpy_docstring()
        else:  # REST
            return self._to_rest_docstring()

    def _to_google_docstring(self) -> str:
        """Convert to Google-style docstring."""
        lines = []
        if self.summary:
            lines.append(self.summary)

        if self.description:
            lines.append("")
            lines.append(self.description)

        for section, content in self.sections.items():
            lines.append("")
            lines.append(f"{section}:")
            lines.append(f"    {content}")

        return "\n".join(lines)

    def _to_numpy_docstring(self) -> str:
        """Convert to NumPy-style docstring."""
        lines = [self.summary]

        if self.description:
            lines.append("")
            lines.append(self.description)

        for section, content in self.sections.items():
            lines.append("")
            lines.append(section)
            lines.append("-" * len(section))
            lines.append(content)

        return "\n".join(lines)

    def _to_rest_docstring(self) -> str:
        """Convert to reST-style docstring."""
        lines = [self.summary]

        if self.description:
            lines.append("")
            lines.append(self.description)

        for section, content in self.sections.items():
            lines.append("")
            lines.append(section)
            lines.append("^" * len(section))
            lines.append(content)

        return "\n".join(lines)


def parse_docstring(
    docstring: str, style: DocstringStyle = DocstringStyle.GOOGLE
) -> ParsedDocstring:
    """Parse a docstring into its components.

    Args:
        docstring: The docstring to parse
        style: The expected docstring style

    Returns:
        ParsedDocstring object containing the parsed components
    """
    if not docstring or not docstring.strip():
        return ParsedDocstring(style=style)

    # Remove leading/trailing triple quotes and whitespace
    docstring = docstring.strip()
    if docstring.startswith('"""'):
        docstring = docstring[3:]
    elif docstring.startswith("'''"):
        docstring = docstring[3:]
    if docstring.endswith('"""'):
        docstring = docstring[:-3]
    elif docstring.endswith("'''"):
        docstring = docstring[:-3]
    docstring = docstring.strip()

    parsed = ParsedDocstring(style=style)

    # Split into summary and the rest
    parts = re.split(r"\n\s*\n", docstring, maxsplit=1)
    parsed.summary = parts[0].strip()

    if len(parts) > 1:
        rest = parts[1].strip()

        # Parse based on style
        if style == DocstringStyle.GOOGLE:
            _parse_google_docstring(rest, parsed)
        elif style == DocstringStyle.NUMPY:
            _parse_numpy_docstring(rest, parsed)
        else:  # REST
            _parse_rest_docstring(rest, parsed)

    return parsed


def _parse_google_docstring(rest: str, parsed: ParsedDocstring) -> None:
    """Parse the rest of a Google-style docstring."""
    current_section: Optional[str] = None
    current_content: list[str] = []

    for line in rest.split("\n"):
        line = line.rstrip()

        # Check for section headers (e.g., "Args:")
        section_match = re.match(r"^(\w+):\s*$", line)
        if section_match:
            if current_section and current_content:
                parsed.sections[current_section] = "\n".join(current_content).strip()
            current_section = section_match.group(1)
            current_content = []
        elif line.startswith("    ") and current_section:
            # Indented line in a section
            current_content.append(line[4:])
        elif current_section:
            # Continuation of section content
            if current_content:
                current_content[-1] += " " + line.lstrip()
            else:
                current_content.append(line.lstrip())
        elif not parsed.description and not current_section:
            # Part of the main description
            if parsed.description:
                parsed.description += "\n" + line
            else:
                parsed.description = line

    # Add the last section
    if current_section and current_content:
        parsed.sections[current_section] = "\n".join(current_content).strip()


def _parse_numpy_docstring(rest: str, parsed: ParsedDocstring) -> None:
    """Parse the rest of a NumPy-style docstring."""
    lines = rest.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Look for section headers (e.g., "Parameters" followed by a line of dashes)
        if i + 1 < len(lines) and lines[i + 1].strip().replace("-", "").strip() == "":
            section = line
            i += 2  # Skip the dash line

            # Collect section content
            content_lines = []
            while i < len(lines) and not (
                lines[i].strip()
                and i + 1 < len(lines)
                and lines[i + 1].strip().replace("-", "").strip() == ""
            ):
                content_lines.append(lines[i].strip())
                i += 1

            parsed.sections[section] = "\n".join(content_lines).strip()
        else:
            if not parsed.description:
                parsed.description = line
            elif line:  # Skip empty lines
                parsed.description += "\n" + line
            i += 1


def _parse_rest_docstring(rest: str, parsed: ParsedDocstring) -> None:
    """Parse the rest of a reST-style docstring."""
    lines = rest.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Look for section headers (e.g., "Parameters" with underline)
        if (
            i > 0
            and i + 1 < len(lines)
            and len(lines[i - 1]) > 0
            and set(lines[i]).issubset(set("=-~_*+#:^\"'`"))
            and len(set(lines[i])) == 1
            and len(lines[i]) >= len(lines[i - 1])
        ):

            section = lines[i - 1].strip()
            i += 1  # Skip the underline

            # Collect section content
            content_lines = []
            while i < len(lines) and not (
                lines[i].strip()
                and i + 1 < len(lines)
                and set(lines[i + 1]).issubset(set("=-~_*+#:^\"'`"))
                and len(set(lines[i + 1])) == 1
                and len(lines[i + 1]) >= len(lines[i])
            ):
                content_lines.append(lines[i].strip())
                i += 1

            parsed.sections[section] = "\n".join(content_lines).strip()
        else:
            if not parsed.description and line:
                if parsed.description:
                    parsed.description += "\n" + line
                else:
                    parsed.description = line
            i += 1
