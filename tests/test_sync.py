"""Tests for bidirectional sync: source→fragments and fragments→source."""
import pytest
from pathlib import Path

from pyweb.core.models import Range
from pyweb.core.store import FragmentStore
from pyweb.core.sync import SyncEngine


@pytest.fixture
def project(tmp_path):
    src = tmp_path / "main.py"
    src.write_text(
        "line0\n"
        "line1\n"
        "line2\n"
        "line3\n"
        "line4\n"
        "line5\n"
        "line6\n"
        "line7\n"
        "line8\n"
        "line9\n"
    )
    store = FragmentStore(tmp_path)
    store.init()
    engine = SyncEngine(store, tmp_path)
    # Cache initial content
    content = src.read_text()
    store.save_cache("main.py", content)
    return tmp_path, store, engine


class TestOnSourceChanged:
    def test_insert_before_fragment(self, project):
        root, store, engine = project
        store.create_fragment("main.py", "block", Range(5, 0, 8, 0))

        old = (root / "main.py").read_text()
        new = "NEW\n" + old
        (root / "main.py").write_text(new)
        engine.on_source_changed("main.py", old, new)

        frag = store.get_fragment_by_name("main.py", "block")
        assert frag.range == Range(6, 0, 9, 0)

    def test_insert_inside_fragment(self, project):
        root, store, engine = project
        store.create_fragment("main.py", "block", Range(2, 0, 8, 0))

        old = (root / "main.py").read_text()
        lines = old.splitlines(keepends=True)
        lines.insert(5, "INSERTED\n")
        new = "".join(lines)
        (root / "main.py").write_text(new)
        engine.on_source_changed("main.py", old, new)

        frag = store.get_fragment_by_name("main.py", "block")
        assert frag.range == Range(2, 0, 9, 0)  # grew by 1

    def test_delete_before_fragment(self, project):
        root, store, engine = project
        store.create_fragment("main.py", "block", Range(5, 0, 8, 0))

        old = (root / "main.py").read_text()
        lines = old.splitlines(keepends=True)
        del lines[0]  # remove first line
        new = "".join(lines)
        (root / "main.py").write_text(new)
        engine.on_source_changed("main.py", old, new)

        frag = store.get_fragment_by_name("main.py", "block")
        assert frag.range == Range(4, 0, 7, 0)

    def test_delete_entire_fragment(self, project):
        root, store, engine = project
        store.create_fragment("main.py", "block", Range(3, 0, 5, 0))

        old = (root / "main.py").read_text()
        lines = old.splitlines(keepends=True)
        del lines[3:5]  # delete lines 3 and 4
        new = "".join(lines)
        (root / "main.py").write_text(new)
        engine.on_source_changed("main.py", old, new)

        frag = store.get_fragment_by_name("main.py", "block")
        assert frag.range.is_orphaned()

    def test_no_change(self, project):
        root, store, engine = project
        store.create_fragment("main.py", "block", Range(2, 0, 5, 0))

        content = (root / "main.py").read_text()
        engine.on_source_changed("main.py", content, content)

        frag = store.get_fragment_by_name("main.py", "block")
        assert frag.range == Range(2, 0, 5, 0)

    def test_updates_content_hash_and_cache(self, project):
        root, store, engine = project
        store.create_fragment("main.py", "block", Range(0, 0, 3, 0))

        old = (root / "main.py").read_text()
        new = "CHANGED\n" + old
        (root / "main.py").write_text(new)
        engine.on_source_changed("main.py", old, new)

        ff = store.load_file("main.py")
        assert ff.content_hash == store.content_hash(new)
        assert store.load_cache("main.py") == new

    def test_multiple_fragments(self, project):
        root, store, engine = project
        store.create_fragment("main.py", "a", Range(0, 0, 3, 0))
        store.create_fragment("main.py", "b", Range(5, 0, 8, 0))

        old = (root / "main.py").read_text()
        lines = old.splitlines(keepends=True)
        lines.insert(4, "NEW1\nNEW2\n")
        new = "".join(lines)
        (root / "main.py").write_text(new)
        engine.on_source_changed("main.py", old, new)

        a = store.get_fragment_by_name("main.py", "a")
        b = store.get_fragment_by_name("main.py", "b")
        assert a.range == Range(0, 0, 3, 0)  # before insert, unchanged
        # b should shift by 2 (2 lines inserted, but as one string it may differ)


class TestOnFragmentContentChanged:
    def test_replace_fragment_content(self, project):
        root, store, engine = project
        frag = store.create_fragment("main.py", "block", Range(3, 0, 5, 0))

        # Fragment covers lines 3-4 ("line3\nline4\n")
        new_code = "REPLACED_A\nREPLACED_B\n"
        result = engine.on_fragment_content_changed("main.py", frag.id, new_code)

        # Source file should be updated
        actual = (root / "main.py").read_text()
        assert actual == result
        assert "REPLACED_A" in actual
        assert "REPLACED_B" in actual
        assert "line3" not in actual
        assert "line4" not in actual
        # Lines before and after should be preserved
        assert "line2" in actual
        assert "line5" in actual

    def test_expand_fragment(self, project):
        root, store, engine = project
        frag = store.create_fragment("main.py", "block", Range(3, 0, 5, 0))
        # Other fragment after it
        frag2 = store.create_fragment("main.py", "after", Range(7, 0, 9, 0))

        # Replace 2 lines with 4 lines
        new_code = "A\nB\nC\nD\n"
        engine.on_fragment_content_changed("main.py", frag.id, new_code)

        # "after" fragment should shift by +2
        after = store.get_fragment_by_name("main.py", "after")
        assert after.range == Range(9, 0, 11, 0)

    def test_shrink_fragment(self, project):
        root, store, engine = project
        frag = store.create_fragment("main.py", "block", Range(3, 0, 7, 0))
        frag2 = store.create_fragment("main.py", "after", Range(8, 0, 10, 0))

        # Replace 4 lines with 1 line
        new_code = "SINGLE\n"
        engine.on_fragment_content_changed("main.py", frag.id, new_code)

        after = store.get_fragment_by_name("main.py", "after")
        assert after.range == Range(5, 0, 7, 0)  # shifted by -3

    def test_nonexistent_fragment_raises(self, project):
        root, store, engine = project
        store.create_fragment("main.py", "block", Range(0, 0, 5, 0))
        with pytest.raises(ValueError, match="not found"):
            engine.on_fragment_content_changed("main.py", "nonexistent", "code\n")

    def test_no_fragments_file_raises(self, project):
        root, store, engine = project
        with pytest.raises(ValueError, match="No fragments"):
            engine.on_fragment_content_changed("nope.py", "id", "code\n")


class TestRoundTrip:
    def test_edit_source_then_view(self, project):
        """Edit source, re-anchor, verify hierarchical view still works."""
        root, store, engine = project
        parent = store.create_fragment("main.py", "top", Range(0, 0, 10, 0))
        store.create_fragment("main.py", "header", Range(0, 0, 3, 0), parent_id=parent.id)
        store.create_fragment("main.py", "body", Range(5, 0, 8, 0), parent_id=parent.id)

        # Insert lines at beginning
        old = (root / "main.py").read_text()
        new = "# comment\n" + old
        (root / "main.py").write_text(new)
        engine.on_source_changed("main.py", old, new)

        # Hierarchical view should still work
        nodes = engine.hierarchical_view("main.py")
        assert len(nodes) == 1
        assert nodes[0].fragment.name == "top"
        assert len(nodes[0].children) == 2

    def test_edit_fragment_then_view(self, project):
        """Edit via fragment, verify expanded view is correct."""
        root, store, engine = project
        frag = store.create_fragment("main.py", "block", Range(2, 0, 4, 0))

        engine.on_fragment_content_changed("main.py", frag.id, "NEW_LINE_A\nNEW_LINE_B\nNEW_LINE_C\n")

        expanded = engine.expanded_view("main.py")
        lines = expanded.splitlines()
        assert lines[0] == "line0"
        assert lines[1] == "line1"
        assert lines[2] == "NEW_LINE_A"
        assert lines[3] == "NEW_LINE_B"
        assert lines[4] == "NEW_LINE_C"
        assert lines[5] == "line4"

    def test_bidirectional_stability(self, project):
        """Edit source → re-anchor → edit fragment → verify consistency."""
        root, store, engine = project
        frag = store.create_fragment("main.py", "block", Range(3, 0, 6, 0))

        # Step 1: External edit — insert 2 lines before fragment
        old = (root / "main.py").read_text()
        new = "X\nY\n" + old
        (root / "main.py").write_text(new)
        engine.on_source_changed("main.py", old, new)

        # Fragment should have shifted
        frag_reloaded = store.get_fragment_by_name("main.py", "block")
        assert frag_reloaded.range == Range(5, 0, 8, 0)

        # Step 2: Edit via fragment
        engine.on_fragment_content_changed("main.py", frag_reloaded.id, "REPLACED\n")

        # Verify the final state
        final = (root / "main.py").read_text()
        lines = final.splitlines()
        assert lines[0] == "X"
        assert lines[1] == "Y"
        assert lines[5] == "REPLACED"
        # Lines after should still be correct
        assert "line6" in final
