"""Tests for DiffAnchorer: computing and applying line edits."""
import pytest
from pyweb.core.models import Range, Fragment
from pyweb.core.anchorer import DiffAnchorer, LineEdit, ORPHAN_RANGE


def frag(name: str, start: int, end: int) -> Fragment:
    """Helper to create a simple line-based fragment."""
    return Fragment(id=name, name=name, file="f.py", range=Range(start, 0, end, 0))


class TestComputeLineEdits:
    def test_identical(self):
        edits = DiffAnchorer.compute_line_edits("a\nb\nc\n", "a\nb\nc\n")
        assert edits == []

    def test_insert_at_end(self):
        edits = DiffAnchorer.compute_line_edits("a\nb\n", "a\nb\nc\n")
        assert len(edits) == 1
        assert edits[0].line == 2
        assert edits[0].old_count == 0
        assert edits[0].new_count == 1

    def test_insert_at_beginning(self):
        edits = DiffAnchorer.compute_line_edits("a\nb\n", "x\na\nb\n")
        assert len(edits) == 1
        assert edits[0].line == 0
        assert edits[0].old_count == 0
        assert edits[0].new_count == 1

    def test_delete_line(self):
        edits = DiffAnchorer.compute_line_edits("a\nb\nc\n", "a\nc\n")
        assert len(edits) == 1
        assert edits[0].line == 1
        assert edits[0].old_count == 1
        assert edits[0].new_count == 0

    def test_replace(self):
        edits = DiffAnchorer.compute_line_edits("a\nb\nc\n", "a\nX\nc\n")
        assert len(edits) == 1
        assert edits[0].old_count == 1
        assert edits[0].new_count == 1

    def test_multiple_hunks(self):
        old = "a\nb\nc\nd\ne\n"
        new = "a\nX\nc\nY\nZ\ne\n"
        edits = DiffAnchorer.compute_line_edits(old, new)
        # Two hunks: replace b→X at line 1, replace d→Y,Z at line 3
        assert len(edits) == 2

    def test_insert_multiple_lines(self):
        edits = DiffAnchorer.compute_line_edits("a\nb\n", "a\nx\ny\nz\nb\n")
        assert len(edits) == 1
        assert edits[0].line == 1
        assert edits[0].old_count == 0
        assert edits[0].new_count == 3

    def test_delete_all(self):
        edits = DiffAnchorer.compute_line_edits("a\nb\nc\n", "")
        assert len(edits) == 1
        assert edits[0].old_count == 3


class TestApplyEdits:
    def test_no_edits(self):
        frags = [frag("a", 0, 5)]
        result = DiffAnchorer.apply_edits(frags, [])
        assert result[0].range == Range(0, 0, 5, 0)

    def test_insert_before_fragment(self):
        """Insert 3 lines at line 0 → fragment shifts down by 3."""
        frags = [frag("a", 5, 10)]
        edits = [LineEdit(line=0, old_count=0, new_count=3)]
        result = DiffAnchorer.apply_edits(frags, edits)
        assert result[0].range == Range(8, 0, 13, 0)

    def test_insert_after_fragment(self):
        """Insert after fragment → no change."""
        frags = [frag("a", 0, 5)]
        edits = [LineEdit(line=10, old_count=0, new_count=3)]
        result = DiffAnchorer.apply_edits(frags, edits)
        assert result[0].range == Range(0, 0, 5, 0)

    def test_insert_inside_fragment(self):
        """Insert 2 lines inside fragment → end grows by 2."""
        frags = [frag("a", 0, 10)]
        edits = [LineEdit(line=5, old_count=0, new_count=2)]
        result = DiffAnchorer.apply_edits(frags, edits)
        assert result[0].range == Range(0, 0, 12, 0)

    def test_delete_before_fragment(self):
        """Delete 2 lines before fragment → fragment shifts up by 2."""
        frags = [frag("a", 5, 10)]
        edits = [LineEdit(line=0, old_count=2, new_count=0)]
        result = DiffAnchorer.apply_edits(frags, edits)
        assert result[0].range == Range(3, 0, 8, 0)

    def test_delete_inside_fragment(self):
        """Delete 3 lines inside fragment → end shrinks by 3."""
        frags = [frag("a", 0, 10)]
        edits = [LineEdit(line=3, old_count=3, new_count=0)]
        result = DiffAnchorer.apply_edits(frags, edits)
        assert result[0].range == Range(0, 0, 7, 0)

    def test_delete_entire_fragment(self):
        """Fragment fully within deletion → orphaned."""
        frags = [frag("a", 3, 7)]
        edits = [LineEdit(line=2, old_count=6, new_count=0)]
        result = DiffAnchorer.apply_edits(frags, edits)
        assert result[0].range.is_orphaned()

    def test_delete_overlapping_start(self):
        """Deletion eats into the start of a fragment."""
        frags = [frag("a", 5, 10)]
        edits = [LineEdit(line=3, old_count=4, new_count=0)]
        # edit deletes lines 3-6 (inclusive). Fragment starts at 5.
        # Lines 5,6 of fragment are eaten. Fragment should start at 3 (edit_start + 0 new), end at 8.
        # Wait: edit_start=3, edit_end=7. Fragment start=5 is within [3,7).
        # lines_eaten_from_start = 7 - 5 = 2.  new start = 3 + 0 = 3. new end = 10 - 2 = 8.
        result = DiffAnchorer.apply_edits(frags, edits)
        assert result[0].range == Range(3, 0, 8, 0)

    def test_delete_overlapping_end(self):
        """Deletion eats into the end of a fragment."""
        frags = [frag("a", 0, 5)]
        edits = [LineEdit(line=3, old_count=4, new_count=0)]
        # edit deletes lines 3-6. Fragment ends at 5 which is within [3,7).
        # Fragment end shrinks to edit_start + new_count = 3 + 0 = 3.
        result = DiffAnchorer.apply_edits(frags, edits)
        assert result[0].range == Range(0, 0, 3, 0)

    def test_replace_inside_fragment(self):
        """Replace 2 lines with 4 inside fragment → net +2."""
        frags = [frag("a", 0, 10)]
        edits = [LineEdit(line=3, old_count=2, new_count=4)]
        result = DiffAnchorer.apply_edits(frags, edits)
        assert result[0].range == Range(0, 0, 12, 0)

    def test_multiple_fragments_multiple_edits(self):
        """Two fragments, insert between them."""
        frags = [frag("a", 0, 5), frag("b", 10, 15)]
        edits = [LineEdit(line=7, old_count=0, new_count=3)]
        result = DiffAnchorer.apply_edits(frags, edits)
        assert result[0].range == Range(0, 0, 5, 0)  # before edit, unchanged
        assert result[1].range == Range(13, 0, 18, 0)  # after edit, shifted

    def test_does_not_mutate_originals(self):
        """apply_edits should not mutate the input fragments."""
        original = frag("a", 5, 10)
        DiffAnchorer.apply_edits([original], [LineEdit(line=0, old_count=0, new_count=3)])
        assert original.range == Range(5, 0, 10, 0)

    def test_orphan_on_full_delete_exact(self):
        """Fragment exactly matches deleted range → orphaned."""
        frags = [frag("a", 3, 6)]
        edits = [LineEdit(line=3, old_count=3, new_count=0)]
        result = DiffAnchorer.apply_edits(frags, edits)
        assert result[0].range.is_orphaned()

    def test_shrink_to_nothing_orphans(self):
        """Fragment shrunk to zero size → orphaned."""
        frags = [frag("a", 5, 6)]  # 1-line fragment
        edits = [LineEdit(line=4, old_count=3, new_count=0)]
        result = DiffAnchorer.apply_edits(frags, edits)
        assert result[0].range.is_orphaned()

    def test_already_orphaned_stays_orphaned(self):
        frags = [Fragment(id="x", name="x", file="f.py", range=ORPHAN_RANGE)]
        edits = [LineEdit(line=0, old_count=0, new_count=5)]
        result = DiffAnchorer.apply_edits(frags, edits)
        assert result[0].range.is_orphaned()


class TestEndToEnd:
    def test_insert_lines_then_apply(self):
        """Full round-trip: compute edits from content change, apply to fragments."""
        old = "line0\nline1\nline2\nline3\nline4\n"
        new = "line0\nNEW1\nNEW2\nline1\nline2\nline3\nline4\n"
        # Inserted 2 lines after line0

        frags = [frag("header", 0, 1), frag("body", 2, 5)]
        edits = DiffAnchorer.compute_line_edits(old, new)
        result = DiffAnchorer.apply_edits(frags, edits)

        assert result[0].range == Range(0, 0, 1, 0)  # header unchanged
        assert result[1].range == Range(4, 0, 7, 0)  # body shifted by 2

    def test_delete_lines_then_apply(self):
        old = "a\nb\nc\nd\ne\nf\n"
        new = "a\nd\ne\nf\n"
        # Deleted lines b, c (lines 1-2)

        frags = [frag("first", 0, 2), frag("second", 3, 6)]
        edits = DiffAnchorer.compute_line_edits(old, new)
        result = DiffAnchorer.apply_edits(frags, edits)

        # first: covered lines 0-2, deletion at lines 1-2 (2 lines deleted inside)
        # end shrinks by 2: Range(0, 0, 0, 0) — but that's empty...
        # Actually end_line is exclusive. Range(0,0,2,0) means lines 0,1.
        # Delete at line 1, count 2 means lines 1,2 deleted.
        # Edit is inside fragment (start=0 <= edit_start=1 and end=2 >= edit_end=3? No, 2 < 3)
        # So this is case 6: edit overlaps end. end_line=2 is within [1, 3).
        # New end = edit_start + new_count = 1 + 0 = 1. start=0, end=1 → still valid
        assert result[0].range == Range(0, 0, 1, 0)
        # second: was at 3-6, edit was at line 1 deleting 2 lines.
        # Fragment entirely after edit_end (3 >= 3), shifted by delta=-2
        assert result[1].range == Range(1, 0, 4, 0)
