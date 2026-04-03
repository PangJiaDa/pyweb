"""Tests for the marker writer: add, remove, rename, prose, resize."""
import pytest
from pyweb.core.writer import add_fragment, remove_fragment, rename_fragment, set_prose, resize_fragment
from pyweb.core.parser import parse_markers, get_fragment_by_id
from pyweb.core.comments import CommentStyle


SIMPLE_SRC = "line0\nline1\nline2\nline3\nline4\n"


class TestAddFragment:
    def test_add_basic(self):
        new_src, fid = add_fragment(SIMPLE_SRC, "main.py", "block", 1, 3)
        result = parse_markers(new_src)
        assert len(result.fragments) == 1
        f = result.fragments[0]
        assert f.name == "block"
        assert f.id == fid
        # Code between markers should be line1, line2
        lines = new_src.splitlines()
        assert "line1" in lines[2]  # after start marker
        assert "line2" in lines[3]

    def test_add_with_prose(self):
        new_src, fid = add_fragment(SIMPLE_SRC, "main.py", "block", 1, 3, prose="Explanation")
        result = parse_markers(new_src)
        f = result.fragments[0]
        assert f.prose == "Explanation"

    def test_add_preserves_surrounding(self):
        new_src, _ = add_fragment(SIMPLE_SRC, "main.py", "block", 1, 3)
        lines = new_src.splitlines()
        assert lines[0] == "line0"
        assert lines[-1] == "line4"

    def test_add_js_style(self):
        js_src = "const a = 1;\nconst b = 2;\nconst c = 3;\n"
        cs = CommentStyle("// ", "")
        new_src, fid = add_fragment(js_src, "main.js", "block", 0, 2, comment_style=cs)
        assert "// @pyweb:start" in new_src
        assert "// @pyweb:end" in new_src

    def test_add_html_style(self):
        html_src = "<div>\n  <p>hi</p>\n</div>\n"
        cs = CommentStyle("<!-- ", " -->")
        new_src, fid = add_fragment(html_src, "index.html", "content", 0, 2, comment_style=cs)
        assert "<!-- @pyweb:start" in new_src
        assert "<!-- @pyweb:end" in new_src
        assert "-->" in new_src

    def test_add_nested(self):
        """Add parent, then add child inside."""
        src, pid = add_fragment(SIMPLE_SRC, "main.py", "parent", 0, 5)
        # Now parse and add child inside (lines shifted by marker insertion)
        # Parent marker is at line 0, code starts at line 1
        src2, cid = add_fragment(src, "main.py", "child", 2, 4)
        result = parse_markers(src2)
        assert len(result.fragments) == 2
        parent = get_fragment_by_id(result.fragments, pid)
        child = get_fragment_by_id(result.fragments, cid)
        assert child.parent_id == pid

    def test_round_trip_parse(self):
        """Add fragment, parse it back, verify all fields."""
        new_src, fid = add_fragment(SIMPLE_SRC, "main.py", "test frag", 2, 4, prose="Some note")
        result = parse_markers(new_src)
        assert len(result.fragments) == 1
        assert result.warnings == []
        f = result.fragments[0]
        assert f.id == fid
        assert f.name == "test frag"
        assert f.prose == "Some note"


class TestRemoveFragment:
    def _make_src_with_fragment(self):
        src, fid = add_fragment(SIMPLE_SRC, "main.py", "block", 1, 3)
        return src, fid

    def test_remove_basic(self):
        src, fid = self._make_src_with_fragment()
        new_src = remove_fragment(src, fid)
        result = parse_markers(new_src)
        assert len(result.fragments) == 0
        # Code should still be there
        assert "line1" in new_src
        assert "line2" in new_src
        assert "@pyweb" not in new_src

    def test_remove_with_prose(self):
        src, fid = add_fragment(SIMPLE_SRC, "main.py", "block", 1, 3, prose="Note")
        new_src = remove_fragment(src, fid)
        assert "@pyweb" not in new_src
        assert "line1" in new_src

    def test_remove_preserves_other_fragments(self):
        src, fid1 = add_fragment(SIMPLE_SRC, "main.py", "first", 0, 2)
        src, fid2 = add_fragment(src, "main.py", "second", 5, 7)
        new_src = remove_fragment(src, fid1)
        result = parse_markers(new_src)
        assert len(result.fragments) == 1
        assert result.fragments[0].id == fid2

    def test_remove_nonexistent_raises(self):
        with pytest.raises(ValueError, match="not found"):
            remove_fragment(SIMPLE_SRC, "nonexistent")


class TestRenameFragment:
    def test_rename(self):
        src, fid = add_fragment(SIMPLE_SRC, "main.py", "old_name", 1, 3)
        new_src = rename_fragment(src, fid, "new_name")
        result = parse_markers(new_src)
        assert result.fragments[0].name == "new_name"
        assert result.fragments[0].id == fid  # ID preserved

    def test_rename_nonexistent_raises(self):
        with pytest.raises(ValueError):
            rename_fragment(SIMPLE_SRC, "nope", "new")


class TestSetProse:
    def test_add_prose(self):
        src, fid = add_fragment(SIMPLE_SRC, "main.py", "block", 1, 3)
        new_src = set_prose(src, "main.py", fid, "New explanation")
        result = parse_markers(new_src)
        assert result.fragments[0].prose == "New explanation"

    def test_replace_prose(self):
        src, fid = add_fragment(SIMPLE_SRC, "main.py", "block", 1, 3, prose="Old")
        new_src = set_prose(src, "main.py", fid, "New")
        result = parse_markers(new_src)
        assert result.fragments[0].prose == "New"
        assert "Old" not in new_src

    def test_remove_prose(self):
        src, fid = add_fragment(SIMPLE_SRC, "main.py", "block", 1, 3, prose="To remove")
        new_src = set_prose(src, "main.py", fid, None)
        result = parse_markers(new_src)
        assert result.fragments[0].prose is None

    def test_multiline_prose(self):
        src, fid = add_fragment(SIMPLE_SRC, "main.py", "block", 1, 3)
        new_src = set_prose(src, "main.py", fid, "Line 1\nLine 2")
        result = parse_markers(new_src)
        assert result.fragments[0].prose == "Line 1\nLine 2"


class TestResizeFragment:
    def test_resize_expand(self):
        src, fid = add_fragment(SIMPLE_SRC, "main.py", "block", 1, 3)
        # Original covers line1-line2. Expand to line0-line3.
        # After marker insertion, actual content is at different lines.
        # Let's work with the marked-up source.
        lines = src.splitlines()
        # Find where the content lines are
        result = parse_markers(src)
        f = result.fragments[0]

        # Resize to cover more: use original line numbers from the marked-up file
        new_src = resize_fragment(src, "main.py", fid, f.content_start_line - 1, f.content_end_line + 1)
        result2 = parse_markers(new_src)
        assert len(result2.fragments) == 1
        f2 = result2.fragments[0]
        assert f2.id == fid
        assert f2.name == "block"

    def test_resize_nonexistent_raises(self):
        with pytest.raises(ValueError):
            resize_fragment(SIMPLE_SRC, "main.py", "nope", 0, 3)


class TestIndentation:
    def test_preserves_indentation(self):
        src = "def foo():\n    x = 1\n    y = 2\n    return x + y\n"
        new_src, fid = add_fragment(src, "main.py", "body", 1, 3)
        lines = new_src.splitlines()
        # Start marker should be indented like line 1
        start_line = [l for l in lines if "@pyweb:start" in l][0]
        assert start_line.startswith("    ")

    def test_no_indentation_at_col_0(self):
        new_src, _ = add_fragment(SIMPLE_SRC, "main.py", "block", 0, 2)
        lines = new_src.splitlines()
        start_line = [l for l in lines if "@pyweb:start" in l][0]
        assert start_line.startswith("# @pyweb")  # no leading spaces
