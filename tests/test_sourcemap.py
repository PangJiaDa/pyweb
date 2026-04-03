"""Tests for SourceMap."""
import pytest
from pyweb.core.models import Range, Fragment, FileFragments
from pyweb.core.sourcemap import SourceMap


def make_ff(fragments: list[Fragment]) -> FileFragments:
    return FileFragments(file="f.py", content_hash="sha256:x", fragments=fragments)


class TestFragmentAt:
    def test_single_root(self):
        f = Fragment(id="r", name="root", file="f.py", range=Range(0, 0, 10, 0))
        sm = SourceMap(make_ff([f]))
        assert sm.fragment_at(5, 0).id == "r"
        assert sm.fragment_at(0, 0).id == "r"
        assert sm.fragment_at(10, 0) is None  # end is exclusive

    def test_nested(self):
        parent = Fragment(id="p", name="parent", file="f.py", range=Range(0, 0, 10, 0), children=["c"])
        child = Fragment(id="c", name="child", file="f.py", range=Range(3, 0, 7, 0))
        sm = SourceMap(make_ff([parent, child]))

        assert sm.fragment_at(1, 0).id == "p"  # in parent, not child
        assert sm.fragment_at(5, 0).id == "c"  # in child (more specific)
        assert sm.fragment_at(8, 0).id == "p"  # after child, still in parent

    def test_outside_all(self):
        f = Fragment(id="r", name="root", file="f.py", range=Range(5, 0, 10, 0))
        sm = SourceMap(make_ff([f]))
        assert sm.fragment_at(2, 0) is None

    def test_multiple_roots(self):
        a = Fragment(id="a", name="a", file="f.py", range=Range(0, 0, 5, 0))
        b = Fragment(id="b", name="b", file="f.py", range=Range(5, 0, 10, 0))
        sm = SourceMap(make_ff([a, b]))
        assert sm.fragment_at(3, 0).id == "a"
        assert sm.fragment_at(7, 0).id == "b"

    def test_inline_fragment(self):
        parent = Fragment(id="p", name="parent", file="f.py", range=Range(5, 0, 6, 0), children=["i"])
        inline = Fragment(id="i", name="inline", file="f.py", range=Range(5, 10, 5, 20))
        sm = SourceMap(make_ff([parent, inline]))
        assert sm.fragment_at(5, 15).id == "i"
        assert sm.fragment_at(5, 5).id == "p"

    def test_orphaned_skipped(self):
        f = Fragment(id="r", name="root", file="f.py", range=Range(-1, -1, -1, -1))
        sm = SourceMap(make_ff([f]))
        assert sm.fragment_at(0, 0) is None


class TestRangeOf:
    def test_found(self):
        f = Fragment(id="r", name="root", file="f.py", range=Range(0, 0, 10, 0))
        sm = SourceMap(make_ff([f]))
        assert sm.range_of("r") == Range(0, 0, 10, 0)

    def test_not_found(self):
        sm = SourceMap(make_ff([]))
        assert sm.range_of("nonexistent") is None


class TestDepthFirstWalk:
    def test_single(self):
        f = Fragment(id="r", name="root", file="f.py", range=Range(0, 0, 10, 0))
        sm = SourceMap(make_ff([f]))
        walk = list(sm.depth_first_walk())
        assert len(walk) == 1
        assert walk[0] == (f, 0)

    def test_nested(self):
        gp = Fragment(id="gp", name="gp", file="f.py", range=Range(0, 0, 20, 0), children=["p"])
        p = Fragment(id="p", name="p", file="f.py", range=Range(2, 0, 15, 0), children=["c"])
        c = Fragment(id="c", name="c", file="f.py", range=Range(5, 0, 10, 0))
        sm = SourceMap(make_ff([gp, p, c]))
        walk = list(sm.depth_first_walk())
        assert [(frag.id, d) for frag, d in walk] == [("gp", 0), ("p", 1), ("c", 2)]

    def test_multiple_roots_siblings(self):
        a = Fragment(id="a", name="a", file="f.py", range=Range(0, 0, 5, 0))
        b = Fragment(id="b", name="b", file="f.py", range=Range(5, 0, 10, 0))
        sm = SourceMap(make_ff([b, a]))  # deliberately out of order
        walk = list(sm.depth_first_walk())
        # Should be sorted by position
        assert walk[0][0].id == "a"
        assert walk[1][0].id == "b"

    def test_orphaned_skipped(self):
        f = Fragment(id="r", name="root", file="f.py", range=Range(-1, -1, -1, -1))
        sm = SourceMap(make_ff([f]))
        walk = list(sm.depth_first_walk())
        assert walk == []


class TestRoots:
    def test_roots(self):
        parent = Fragment(id="p", name="p", file="f.py", range=Range(0, 0, 10, 0), children=["c"])
        child = Fragment(id="c", name="c", file="f.py", range=Range(2, 0, 5, 0))
        sm = SourceMap(make_ff([parent, child]))
        roots = sm.roots
        assert len(roots) == 1
        assert roots[0].id == "p"
