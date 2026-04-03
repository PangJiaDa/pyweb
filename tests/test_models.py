"""Tests for core data models: Range, Fragment, FileFragments."""
import json
import pytest
from pyweb.core.models import Range, Fragment, FileFragments


class TestRange:
    def test_contains_same(self):
        r = Range(0, 0, 10, 0)
        assert r.contains(r)

    def test_contains_inner(self):
        outer = Range(0, 0, 10, 0)
        inner = Range(2, 0, 8, 0)
        assert outer.contains(inner)
        assert not inner.contains(outer)

    def test_contains_col_level(self):
        outer = Range(5, 0, 5, 20)
        inner = Range(5, 3, 5, 15)
        assert outer.contains(inner)
        assert not inner.contains(outer)

    def test_not_contains_partial(self):
        a = Range(0, 0, 5, 0)
        b = Range(3, 0, 8, 0)
        assert not a.contains(b)
        assert not b.contains(a)

    def test_overlaps_yes(self):
        a = Range(0, 0, 5, 0)
        b = Range(3, 0, 8, 0)
        assert a.overlaps(b)
        assert b.overlaps(a)

    def test_overlaps_no_adjacent(self):
        a = Range(0, 0, 5, 0)
        b = Range(5, 0, 10, 0)
        assert not a.overlaps(b)
        assert not b.overlaps(a)

    def test_overlaps_no_disjoint(self):
        a = Range(0, 0, 3, 0)
        b = Range(5, 0, 10, 0)
        assert not a.overlaps(b)

    def test_overlaps_inline(self):
        a = Range(5, 0, 5, 10)
        b = Range(5, 5, 5, 15)
        assert a.overlaps(b)

    def test_overlaps_inline_no(self):
        a = Range(5, 0, 5, 10)
        b = Range(5, 10, 5, 20)
        assert not a.overlaps(b)

    def test_is_orphaned(self):
        assert Range(-1, -1, -1, -1).is_orphaned()
        assert not Range(0, 0, 5, 0).is_orphaned()

    def test_round_trip_dict(self):
        r = Range(1, 2, 3, 4)
        assert Range.from_dict(r.to_dict()) == r


class TestFragment:
    def test_round_trip_dict(self):
        f = Fragment(
            id="abc123",
            name="test",
            file="src/main.py",
            range=Range(0, 0, 10, 0),
            children=["child1", "child2"],
            prose="Some explanation",
        )
        restored = Fragment.from_dict(f.to_dict())
        assert restored.id == f.id
        assert restored.name == f.name
        assert restored.file == f.file
        assert restored.range == f.range
        assert restored.children == f.children
        assert restored.prose == f.prose

    def test_defaults(self):
        f = Fragment(id="x", name="n", file="f", range=Range(0, 0, 1, 0))
        assert f.children == []
        assert f.prose is None

    def test_from_dict_missing_optional(self):
        d = {
            "id": "x",
            "name": "n",
            "file": "f",
            "range": {"start_line": 0, "start_col": 0, "end_line": 1, "end_col": 0},
        }
        f = Fragment.from_dict(d)
        assert f.children == []
        assert f.prose is None


class TestFileFragments:
    def test_round_trip_json(self):
        ff = FileFragments(
            file="src/main.py",
            content_hash="sha256:abc",
            fragments=[
                Fragment(
                    id="f1",
                    name="init",
                    file="src/main.py",
                    range=Range(0, 0, 10, 0),
                    children=["f2"],
                    prose="Setup code",
                ),
                Fragment(
                    id="f2",
                    name="logging",
                    file="src/main.py",
                    range=Range(2, 0, 8, 0),
                ),
            ],
        )
        json_str = ff.to_json()
        restored = FileFragments.from_json(json_str)
        assert restored.file == ff.file
        assert restored.content_hash == ff.content_hash
        assert len(restored.fragments) == 2
        assert restored.fragments[0].name == "init"
        assert restored.fragments[1].name == "logging"
        assert restored.fragments[0].children == ["f2"]

    def test_empty_fragments(self):
        ff = FileFragments(file="a.py", content_hash="sha256:x")
        j = ff.to_json()
        restored = FileFragments.from_json(j)
        assert restored.fragments == []

    def test_valid_json(self):
        ff = FileFragments(file="a.py", content_hash="sha256:x", fragments=[])
        parsed = json.loads(ff.to_json())
        assert "file" in parsed
        assert "content_hash" in parsed
        assert "fragments" in parsed
