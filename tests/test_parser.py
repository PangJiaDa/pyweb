"""Tests for the marker-based parser."""
import pytest
from pyweb.core.parser import parse_markers, get_roots, get_fragment_by_id, get_fragment_by_name


class TestParseBasic:
    def test_single_fragment(self):
        src = (
            'x = 1\n'
            '# @pyweb:start id="f1" name="init"\n'
            'y = 2\n'
            'z = 3\n'
            '# @pyweb:end id="f1"\n'
            'w = 4\n'
        )
        result = parse_markers(src)
        assert len(result.fragments) == 1
        assert result.warnings == []

        f = result.fragments[0]
        assert f.id == "f1"
        assert f.name == "init"
        assert f.start_line == 1
        assert f.end_line == 5  # exclusive
        assert f.content_start_line == 2
        assert f.content_end_line == 4
        assert f.parent_id is None
        assert f.children == []

    def test_nested_fragments(self):
        src = (
            '# @pyweb:start id="p" name="parent"\n'
            'a = 1\n'
            '# @pyweb:start id="c" name="child"\n'
            'b = 2\n'
            '# @pyweb:end id="c"\n'
            'c = 3\n'
            '# @pyweb:end id="p"\n'
        )
        result = parse_markers(src)
        assert len(result.fragments) == 2
        assert result.warnings == []

        parent = get_fragment_by_id(result.fragments, "p")
        child = get_fragment_by_id(result.fragments, "c")
        assert parent is not None
        assert child is not None
        assert child.parent_id == "p"
        assert "c" in parent.children
        assert child.parent_id == "p"

    def test_deeply_nested(self):
        src = (
            '# @pyweb:start id="a" name="a"\n'
            '# @pyweb:start id="b" name="b"\n'
            '# @pyweb:start id="c" name="c"\n'
            'x = 1\n'
            '# @pyweb:end id="c"\n'
            '# @pyweb:end id="b"\n'
            '# @pyweb:end id="a"\n'
        )
        result = parse_markers(src)
        assert len(result.fragments) == 3

        a = get_fragment_by_id(result.fragments, "a")
        b = get_fragment_by_id(result.fragments, "b")
        c = get_fragment_by_id(result.fragments, "c")
        assert a.children == ["b"]
        assert b.children == ["c"]
        assert c.children == []
        assert b.parent_id == "a"
        assert c.parent_id == "b"

    def test_siblings(self):
        src = (
            '# @pyweb:start id="p" name="parent"\n'
            '# @pyweb:start id="c1" name="child1"\n'
            'a = 1\n'
            '# @pyweb:end id="c1"\n'
            '# @pyweb:start id="c2" name="child2"\n'
            'b = 2\n'
            '# @pyweb:end id="c2"\n'
            '# @pyweb:end id="p"\n'
        )
        result = parse_markers(src)
        assert len(result.fragments) == 3

        p = get_fragment_by_id(result.fragments, "p")
        assert p.children == ["c1", "c2"]

    def test_no_fragments(self):
        result = parse_markers("x = 1\ny = 2\n")
        assert result.fragments == []
        assert result.warnings == []


class TestProse:
    def test_prose_lines(self):
        src = (
            '# @pyweb:start id="f1" name="init"\n'
            '# @pyweb:prose This sets up logging.\n'
            '# @pyweb:prose Very important.\n'
            'x = 1\n'
            '# @pyweb:end id="f1"\n'
        )
        result = parse_markers(src)
        f = result.fragments[0]
        assert f.prose == "This sets up logging.\nVery important."
        assert f.content_start_line == 3  # after prose

    def test_no_prose(self):
        src = (
            '# @pyweb:start id="f1" name="init"\n'
            'x = 1\n'
            '# @pyweb:end id="f1"\n'
        )
        result = parse_markers(src)
        assert result.fragments[0].prose is None

    def test_prose_outside_fragment(self):
        src = (
            '# @pyweb:prose orphaned prose\n'
            'x = 1\n'
        )
        result = parse_markers(src)
        assert len(result.warnings) == 1
        assert "outside" in result.warnings[0].message


class TestCommentStyles:
    def test_js_style(self):
        src = (
            '// @pyweb:start id="f1" name="init"\n'
            'const x = 1;\n'
            '// @pyweb:end id="f1"\n'
        )
        result = parse_markers(src)
        assert len(result.fragments) == 1
        assert result.fragments[0].name == "init"

    def test_html_style(self):
        src = (
            '<!-- @pyweb:start id="f1" name="header" -->\n'
            '<h1>Hello</h1>\n'
            '<!-- @pyweb:end id="f1" -->\n'
        )
        result = parse_markers(src)
        assert len(result.fragments) == 1
        assert result.fragments[0].name == "header"

    def test_css_style(self):
        src = (
            '/* @pyweb:start id="f1" name="reset" */\n'
            '* { margin: 0; }\n'
            '/* @pyweb:end id="f1" */\n'
        )
        result = parse_markers(src)
        assert len(result.fragments) == 1

    def test_lua_style(self):
        src = (
            '-- @pyweb:start id="f1" name="init"\n'
            'local x = 1\n'
            '-- @pyweb:end id="f1"\n'
        )
        result = parse_markers(src)
        assert len(result.fragments) == 1

    def test_html_prose(self):
        src = (
            '<!-- @pyweb:start id="f1" name="nav" -->\n'
            '<!-- @pyweb:prose Navigation bar component -->\n'
            '<nav>stuff</nav>\n'
            '<!-- @pyweb:end id="f1" -->\n'
        )
        result = parse_markers(src)
        assert result.fragments[0].prose == "Navigation bar component"


class TestPartialParse:
    def test_missing_end_extends_to_eof(self):
        src = (
            '# @pyweb:start id="f1" name="init"\n'
            'x = 1\n'
            'y = 2\n'
        )
        result = parse_markers(src)
        assert len(result.fragments) == 1
        f = result.fragments[0]
        assert f.end_line == 3  # EOF
        assert len(result.warnings) == 1
        assert "never closed" in result.warnings[0].message

    def test_orphaned_end(self):
        src = (
            'x = 1\n'
            '# @pyweb:end id="f1"\n'
        )
        result = parse_markers(src)
        assert result.fragments == []
        assert len(result.warnings) == 1
        assert "unknown" in result.warnings[0].message

    def test_missing_inner_end_auto_closes(self):
        src = (
            '# @pyweb:start id="p" name="parent"\n'
            '# @pyweb:start id="c" name="child"\n'
            'x = 1\n'
            '# @pyweb:end id="p"\n'
        )
        result = parse_markers(src)
        assert len(result.fragments) == 2

        child = get_fragment_by_id(result.fragments, "c")
        parent = get_fragment_by_id(result.fragments, "p")
        # Child should be auto-closed at parent's end
        assert child.end_line == 3  # the line of parent's end marker
        assert len(result.warnings) == 1
        assert "auto-closed" in result.warnings[0].message

    def test_duplicate_id(self):
        src = (
            '# @pyweb:start id="f1" name="first"\n'
            '# @pyweb:end id="f1"\n'
            '# @pyweb:start id="f1" name="second"\n'
            '# @pyweb:end id="f1"\n'
        )
        result = parse_markers(src)
        assert len(result.fragments) == 1  # second is skipped
        assert len(result.warnings) == 1
        assert "Duplicate" in result.warnings[0].message


class TestGetRoots:
    def test_roots(self):
        src = (
            '# @pyweb:start id="p" name="parent"\n'
            '# @pyweb:start id="c" name="child"\n'
            '# @pyweb:end id="c"\n'
            '# @pyweb:end id="p"\n'
        )
        result = parse_markers(src)
        roots = get_roots(result.fragments)
        assert len(roots) == 1
        assert roots[0].id == "p"

    def test_multiple_roots(self):
        src = (
            '# @pyweb:start id="a" name="a"\n'
            '# @pyweb:end id="a"\n'
            '# @pyweb:start id="b" name="b"\n'
            '# @pyweb:end id="b"\n'
        )
        result = parse_markers(src)
        roots = get_roots(result.fragments)
        assert len(roots) == 2


class TestGetByName:
    def test_found(self):
        src = (
            '# @pyweb:start id="f1" name="init"\n'
            '# @pyweb:end id="f1"\n'
        )
        result = parse_markers(src)
        f = get_fragment_by_name(result.fragments, "init")
        assert f is not None
        assert f.id == "f1"

    def test_not_found(self):
        result = parse_markers('x = 1\n')
        assert get_fragment_by_name(result.fragments, "nope") is None


class TestToFragment:
    def test_converts(self):
        src = (
            '# @pyweb:start id="f1" name="init"\n'
            '# @pyweb:prose Explanation here\n'
            'x = 1\n'
            '# @pyweb:end id="f1"\n'
        )
        result = parse_markers(src)
        pf = result.fragments[0]
        frag = pf.to_fragment("main.py")
        assert frag.id == "f1"
        assert frag.name == "init"
        assert frag.file == "main.py"
        assert frag.range.start_line == 0
        assert frag.range.end_line == 4
        assert frag.prose == "Explanation here"
