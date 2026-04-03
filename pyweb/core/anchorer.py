from __future__ import annotations

import difflib
from dataclasses import dataclass

from pyweb.core.models import Fragment, Range


@dataclass
class LineEdit:
    """A contiguous edit: at `line` in the old file, delete `old_count` lines, insert `new_count` lines."""
    line: int
    old_count: int
    new_count: int


ORPHAN_RANGE = Range(-1, -1, -1, -1)


class DiffAnchorer:

    @staticmethod
    def compute_line_edits(old_content: str, new_content: str) -> list[LineEdit]:
        """Compute a list of line edits that transform old_content into new_content.

        Uses difflib.SequenceMatcher on lines. Returns edits sorted by line number
        in the old file (ascending). Each edit represents a contiguous hunk:
        delete `old_count` lines starting at `line`, insert `new_count` lines.
        """
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
        edits: list[LineEdit] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            elif tag == "replace":
                edits.append(LineEdit(line=i1, old_count=i2 - i1, new_count=j2 - j1))
            elif tag == "delete":
                edits.append(LineEdit(line=i1, old_count=i2 - i1, new_count=0))
            elif tag == "insert":
                edits.append(LineEdit(line=i1, old_count=0, new_count=j2 - j1))

        return edits

    @staticmethod
    def apply_edits(fragments: list[Fragment], edits: list[LineEdit]) -> list[Fragment]:
        """Apply line edits to fragment ranges, shifting/shrinking them as needed.

        Returns new list of fragments with updated ranges.
        Fragments fully deleted get ORPHAN_RANGE (-1,-1,-1,-1).

        Edits must be sorted by line ascending (as compute_line_edits returns).
        We process edits in reverse order so earlier edits don't affect the line
        numbers of later edits.
        """
        # Work on copies
        result = []
        for f in fragments:
            result.append(Fragment(
                id=f.id,
                name=f.name,
                file=f.file,
                range=Range(f.range.start_line, f.range.start_col,
                            f.range.end_line, f.range.end_col),
                children=list(f.children),
                prose=f.prose,
            ))

        # Process edits in reverse order (highest line first) so shifts don't interfere
        for edit in reversed(edits):
            delta = edit.new_count - edit.old_count
            edit_start = edit.line
            edit_end = edit.line + edit.old_count  # exclusive end in old file

            for frag in result:
                r = frag.range
                if r.is_orphaned():
                    continue

                # Case 1: fragment is entirely after the edit → shift
                if r.start_line >= edit_end:
                    r.start_line += delta
                    r.end_line += delta

                # Case 2: fragment is entirely before the edit → no change
                elif r.end_line <= edit_start:
                    pass

                # Case 3: edit is entirely within the fragment → adjust end
                elif r.start_line <= edit_start and r.end_line >= edit_end:
                    r.end_line += delta
                    if r.start_line >= r.end_line:
                        frag.range = ORPHAN_RANGE

                # Case 4: fragment is entirely within the deleted region → orphan
                elif edit_start <= r.start_line and r.end_line <= edit_end:
                    frag.range = ORPHAN_RANGE

                # Case 5: edit overlaps start of fragment
                elif edit_start <= r.start_line < edit_end:
                    # Lines before fragment start that were deleted
                    lines_eaten_from_start = edit_end - r.start_line
                    r.start_line = edit_start + edit.new_count
                    r.end_line -= lines_eaten_from_start
                    r.end_line += 0  # no additional shift needed; the eaten lines are gone
                    if r.start_line >= r.end_line:
                        frag.range = ORPHAN_RANGE

                # Case 6: edit overlaps end of fragment
                elif edit_start < r.end_line <= edit_end:
                    # Shrink the fragment to end at edit_start
                    r.end_line = edit_start + edit.new_count
                    if r.start_line >= r.end_line:
                        frag.range = ORPHAN_RANGE

        return result
