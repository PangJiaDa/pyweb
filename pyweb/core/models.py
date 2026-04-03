from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Range:
    start_line: int  # 0-indexed
    start_col: int   # 0-indexed
    end_line: int     # 0-indexed, exclusive
    end_col: int      # 0-indexed, exclusive

    def contains(self, other: Range) -> bool:
        """True if self fully contains other."""
        self_start = (self.start_line, self.start_col)
        self_end = (self.end_line, self.end_col)
        other_start = (other.start_line, other.start_col)
        other_end = (other.end_line, other.end_col)
        return self_start <= other_start and other_end <= self_end

    def overlaps(self, other: Range) -> bool:
        """True if self and other overlap (share any position)."""
        self_start = (self.start_line, self.start_col)
        self_end = (self.end_line, self.end_col)
        other_start = (other.start_line, other.start_col)
        other_end = (other.end_line, other.end_col)
        # No overlap if one ends before the other starts
        if self_end <= other_start or other_end <= self_start:
            return False
        return True

    def is_orphaned(self) -> bool:
        return (self.start_line == -1 and self.start_col == -1
                and self.end_line == -1 and self.end_col == -1)

    def to_dict(self) -> dict:
        return {
            "start_line": self.start_line,
            "start_col": self.start_col,
            "end_line": self.end_line,
            "end_col": self.end_col,
        }

    @staticmethod
    def from_dict(d: dict) -> Range:
        return Range(
            start_line=d["start_line"],
            start_col=d["start_col"],
            end_line=d["end_line"],
            end_col=d["end_col"],
        )


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class Fragment:
    id: str
    name: str
    file: str           # relative path
    range: Range
    children: list[str] = field(default_factory=list)  # ordered child IDs
    prose: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "file": self.file,
            "range": self.range.to_dict(),
            "children": self.children,
            "prose": self.prose,
        }

    @staticmethod
    def from_dict(d: dict) -> Fragment:
        return Fragment(
            id=d["id"],
            name=d["name"],
            file=d["file"],
            range=Range.from_dict(d["range"]),
            children=d.get("children", []),
            prose=d.get("prose"),
        )


@dataclass
class FileFragments:
    file: str
    content_hash: str
    fragments: list[Fragment] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "content_hash": self.content_hash,
            "fragments": [f.to_dict() for f in self.fragments],
        }

    @staticmethod
    def from_dict(d: dict) -> FileFragments:
        return FileFragments(
            file=d["file"],
            content_hash=d["content_hash"],
            fragments=[Fragment.from_dict(f) for f in d.get("fragments", [])],
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @staticmethod
    def from_json(text: str) -> FileFragments:
        return FileFragments.from_dict(json.loads(text))
