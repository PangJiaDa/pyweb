"""Tests for hierarchical view rendering and SyncEngine views."""
import pytest
from pathlib import Path

from pyweb.core.models import Range
from pyweb.core.store import FragmentStore
from pyweb.core.sync import SyncEngine


@pytest.fixture
def project(tmp_path):
    src = tmp_path / "main.py"
    src.write_text(
        "import os\n"
        "import sys\n"
        "\n"
        "def main():\n"
        "    x = 1\n"
        "    y = 2\n"
        "    print(x + y)\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    store = FragmentStore(tmp_path)
    store.init()
    engine = SyncEngine(store, tmp_path)
    return tmp_path, store, engine


class TestHierarchicalView:
    def test_single_root(self, project):
        root, store, engine = project
        store.create_fragment("main.py", "imports", Range(0, 0, 2, 0))
        nodes = engine.hierarchical_view("main.py")
        assert len(nodes) == 1
        assert nodes[0].fragment.name == "imports"
        assert "import os" in nodes[0].code
        assert "import sys" in nodes[0].code

    def test_nested_fragments(self, project):
        root, store, engine = project
        p = store.create_fragment("main.py", "main func", Range(3, 0, 8, 0))
        store.create_fragment("main.py", "setup", Range(4, 0, 6, 0), parent_id=p.id)
        store.create_fragment("main.py", "output", Range(6, 0, 7, 0), parent_id=p.id)

        nodes = engine.hierarchical_view("main.py")
        assert len(nodes) == 1
        main_node = nodes[0]
        assert main_node.fragment.name == "main func"
        assert len(main_node.children) == 2
        assert main_node.children[0].fragment.name == "setup"
        assert main_node.children[1].fragment.name == "output"

    def test_owned_code_excludes_children(self, project):
        root, store, engine = project
        p = store.create_fragment("main.py", "all", Range(0, 0, 10, 0))
        store.create_fragment("main.py", "imports", Range(0, 0, 2, 0), parent_id=p.id)

        nodes = engine.hierarchical_view("main.py")
        parent_node = nodes[0]
        # Parent's owned code should NOT include lines 0-1 (those belong to "imports")
        assert "import os" not in parent_node.code
        # But should include lines 2-9
        assert "def main()" in parent_node.code

    def test_empty_file(self, project):
        root, store, engine = project
        nodes = engine.hierarchical_view("main.py")
        assert nodes == []  # no fragments defined

    def test_nonexistent_file(self, project):
        root, store, engine = project
        nodes = engine.hierarchical_view("nope.py")
        assert nodes == []


class TestRenderHierarchicalText:
    def test_render_root(self, project):
        root, store, engine = project
        store.create_fragment("main.py", "imports", Range(0, 0, 2, 0))
        text = engine.render_hierarchical_text("main.py")
        assert "=== imports ===" in text
        assert "import os" in text

    def test_render_nested(self, project):
        root, store, engine = project
        p = store.create_fragment("main.py", "program", Range(0, 0, 10, 0))
        store.create_fragment("main.py", "imports", Range(0, 0, 2, 0), parent_id=p.id)

        text = engine.render_hierarchical_text("main.py")
        assert "=== program ===" in text
        assert "--- imports ---" in text  # nested

    def test_render_with_prose(self, project):
        root, store, engine = project
        store.create_fragment("main.py", "imports", Range(0, 0, 2, 0), prose="Standard library imports")
        text = engine.render_hierarchical_text("main.py")
        assert "Standard library imports" in text

    def test_render_specific_fragment(self, project):
        root, store, engine = project
        store.create_fragment("main.py", "imports", Range(0, 0, 2, 0))
        p = store.create_fragment("main.py", "main func", Range(3, 0, 8, 0))

        text = engine.render_hierarchical_text("main.py", fragment_id=p.id)
        assert "main func" in text
        assert "imports" not in text

    def test_render_by_name(self, project):
        root, store, engine = project
        store.create_fragment("main.py", "imports", Range(0, 0, 2, 0))
        text = engine.render_hierarchical_text("main.py", fragment_id="imports")
        assert "imports" in text

    def test_render_not_found(self, project):
        root, store, engine = project
        text = engine.render_hierarchical_text("main.py", fragment_id="nonexistent")
        assert "not found" in text.lower()

    def test_render_no_fragments(self, project):
        root, store, engine = project
        text = engine.render_hierarchical_text("main.py")
        assert text == ""


class TestExpandedView:
    def test_expanded_view(self, project):
        root, store, engine = project
        content = engine.expanded_view("main.py")
        assert "import os" in content
        assert "import sys" in content
        assert "def main():" in content
