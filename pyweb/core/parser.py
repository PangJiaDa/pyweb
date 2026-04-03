"""Parse @pyweb markers from source files and build fragment tree.

Marker format (within any comment style):
    @pyweb:start id="<id>" name="<name>"
    @pyweb:prose <text>
    @pyweb:end id="<id>"

Parsing uses a stack to infer parent-child nesting.
Handles partial/corrupted markers gracefully.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from pyweb.core.models import Range, Fragment

# These regexes match anywhere in a line, regardless of comment syntax
START_RE = re.compile(r'@pyweb:start\s+id="(?P<id>[^"]+)"\s+name="(?P<name>[^"]+)"')
PROSE_RE = re.compile(r'@pyweb:prose\s+(?P<text>.+?)(?:\s*-->|\s*\*/|\s*)$')
END_RE = re.compile(r'@pyweb:end\s+id="(?P<id>[^"]+)"')


@dataclass
class ParsedFragment:
    """A fragment extracted from source markers."""
    id: str
    name: str
    start_line: int          # line of the @pyweb:start marker (0-indexed)
    end_line: int             # line AFTER the @pyweb:end marker (0-indexed, exclusive)
    content_start_line: int   # first line of actual code (after start marker + prose)
    content_end_line: int     # last line of actual code (the @pyweb:end marker line)
    children: list[str] = field(default_factory=list)
    prose_lines: list[str] = field(default_factory=list)
    parent_id: str | None = None

    @property
    def prose(self) -> str | None:
        if not self.prose_lines:
            return None
        return "\n".join(self.prose_lines)

    def to_fragment(self, file_path: str) -> Fragment:
        return Fragment(
            id=self.id,
            name=self.name,
            file=file_path,
            range=Range(self.start_line, 0, self.end_line, 0),
            children=list(self.children),
            prose=self.prose,
        )


@dataclass
class ParseWarning:
    line: int
    message: str


@dataclass
class ParseResult:
    fragments: list[ParsedFragment]
    warnings: list[ParseWarning]


def parse_markers(source: str, file_path: str = "") -> ParseResult:
    """Parse @pyweb markers from source text.

    Returns ParseResult with fragments and any warnings about malformed markers.
    Handles partial/corrupted markers gracefully:
    - Missing end → fragment extends to parent's end or EOF
    - Orphaned end → ignored with warning
    - Prose outside fragment → ignored with warning
    """
    lines = source.splitlines(keepends=True)
    fragments: dict[str, ParsedFragment] = {}
    stack: list[str] = []  # stack of fragment IDs (innermost on top)
    warnings: list[ParseWarning] = []

    # Track which fragment is currently collecting prose
    collecting_prose_for: str | None = None

    for lineno, line in enumerate(lines):
        start_match = START_RE.search(line)
        end_match = END_RE.search(line)
        prose_match = PROSE_RE.search(line)

        if start_match:
            fid = start_match.group("id")
            fname = start_match.group("name")

            if fid in fragments:
                warnings.append(ParseWarning(lineno, f"Duplicate fragment ID '{fid}'"))
                continue

            parent_id = stack[-1] if stack else None
            pf = ParsedFragment(
                id=fid,
                name=fname,
                start_line=lineno,
                end_line=-1,  # will be set when end marker is found
                content_start_line=lineno + 1,  # tentative, adjusted after prose
                content_end_line=-1,
                parent_id=parent_id,
            )
            fragments[fid] = pf

            if parent_id and parent_id in fragments:
                fragments[parent_id].children.append(fid)

            stack.append(fid)
            collecting_prose_for = fid

        elif end_match:
            fid = end_match.group("id")
            collecting_prose_for = None

            if fid not in fragments:
                warnings.append(ParseWarning(lineno, f"End marker for unknown fragment '{fid}'"))
                continue

            pf = fragments[fid]
            pf.end_line = lineno + 1  # exclusive
            pf.content_end_line = lineno

            # Pop stack up to and including this fragment
            # (handles missing end markers for inner fragments)
            while stack:
                popped = stack.pop()
                if popped == fid:
                    break
                # Auto-close unclosed inner fragment
                inner = fragments[popped]
                if inner.end_line == -1:
                    inner.end_line = lineno
                    inner.content_end_line = lineno
                    warnings.append(ParseWarning(
                        lineno,
                        f"Fragment '{inner.name}' ({popped}) auto-closed at end of '{pf.name}'"
                    ))

        elif prose_match and collecting_prose_for:
            pf = fragments[collecting_prose_for]
            pf.prose_lines.append(prose_match.group("text").rstrip())
            pf.content_start_line = lineno + 1

        elif prose_match and not collecting_prose_for:
            warnings.append(ParseWarning(lineno, "Prose marker outside any fragment"))

    # Close any unclosed fragments at EOF
    while stack:
        fid = stack.pop()
        pf = fragments[fid]
        if pf.end_line == -1:
            pf.end_line = len(lines)
            pf.content_end_line = len(lines)
            warnings.append(ParseWarning(
                len(lines) - 1,
                f"Fragment '{pf.name}' ({fid}) never closed, extends to EOF"
            ))

    result_frags = list(fragments.values())
    return ParseResult(fragments=result_frags, warnings=warnings)


def get_roots(fragments: list[ParsedFragment]) -> list[ParsedFragment]:
    """Get root fragments (those with no parent)."""
    return [f for f in fragments if f.parent_id is None]


def get_fragment_by_id(fragments: list[ParsedFragment], fid: str) -> ParsedFragment | None:
    for f in fragments:
        if f.id == fid:
            return f
    return None


def get_fragment_by_name(fragments: list[ParsedFragment], name: str) -> ParsedFragment | None:
    for f in fragments:
        if f.name == name:
            return f
    return None
