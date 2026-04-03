from __future__ import annotations

from collections.abc import Iterator

from pyweb.core.models import FileFragments, Fragment, Range


class SourceMap:
    """In-memory bidirectional mapping between source positions and fragments.

    Built from a FileFragments structure. Provides:
    - Position → deepest owning fragment
    - Fragment ID → range
    - Depth-first iteration of the fragment tree
    """

    def __init__(self, file_frags: FileFragments) -> None:
        self._frags_by_id: dict[str, Fragment] = {f.id: f for f in file_frags.fragments}
        self._roots: list[Fragment] = self._compute_roots(file_frags)

    @staticmethod
    def _compute_roots(ff: FileFragments) -> list[Fragment]:
        child_ids: set[str] = set()
        for f in ff.fragments:
            child_ids.update(f.children)
        roots = [f for f in ff.fragments if f.id not in child_ids and not f.range.is_orphaned()]
        roots.sort(key=lambda f: (f.range.start_line, f.range.start_col))
        return roots

    def fragment_at(self, line: int, col: int) -> Fragment | None:
        """Return the deepest (most specific) fragment containing (line, col)."""
        pos = (line, col)

        def search(fragment_ids: list[str]) -> Fragment | None:
            for fid in fragment_ids:
                f = self._frags_by_id.get(fid)
                if f is None or f.range.is_orphaned():
                    continue
                start = (f.range.start_line, f.range.start_col)
                end = (f.range.end_line, f.range.end_col)
                if start <= pos < end:
                    # Check children for a more specific match
                    child_match = search(f.children)
                    return child_match if child_match is not None else f
            return None

        # Search roots first
        root_ids = [f.id for f in self._roots]
        return search(root_ids)

    def range_of(self, fragment_id: str) -> Range | None:
        f = self._frags_by_id.get(fragment_id)
        return f.range if f else None

    def depth_first_walk(self) -> Iterator[tuple[Fragment, int]]:
        """Yield (fragment, depth) pairs in depth-first order."""
        def walk(fid: str, depth: int) -> Iterator[tuple[Fragment, int]]:
            f = self._frags_by_id.get(fid)
            if f is None or f.range.is_orphaned():
                return
            yield (f, depth)
            for cid in f.children:
                yield from walk(cid, depth + 1)

        for root in self._roots:
            yield from walk(root.id, 0)

    @property
    def roots(self) -> list[Fragment]:
        return list(self._roots)
