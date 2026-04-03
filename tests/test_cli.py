"""Tests for CLI commands."""
import json
import pytest
from pathlib import Path
from click.testing import CliRunner

from pyweb.cli import cli
from pyweb.core.store import FragmentStore


@pytest.fixture
def project(tmp_path):
    """Create a temp project with a source file."""
    src = tmp_path / "main.py"
    src.write_text("line0\nline1\nline2\nline3\nline4\nline5\nline6\nline7\nline8\nline9\n")
    return tmp_path


@pytest.fixture
def runner():
    return CliRunner()


def invoke(runner, project, args):
    return runner.invoke(cli, ["-p", str(project)] + args)


class TestInit:
    def test_init(self, runner, project):
        result = invoke(runner, project, ["init"])
        assert result.exit_code == 0
        assert "Initialized" in result.output
        assert (project / ".pyweb" / "config.json").exists()
        assert (project / ".pyweb" / "fragments").is_dir()

    def test_init_creates_gitignore_entry(self, runner, project):
        invoke(runner, project, ["init"])
        gitignore = (project / ".gitignore").read_text()
        assert ".pyweb/cache/" in gitignore

    def test_init_idempotent(self, runner, project):
        invoke(runner, project, ["init"])
        result = invoke(runner, project, ["init"])
        assert result.exit_code == 0


class TestAdd:
    def test_add_fragment(self, runner, project):
        invoke(runner, project, ["init"])
        result = invoke(runner, project, ["add", "main.py", "header", "0", "3"])
        assert result.exit_code == 0
        assert "Created fragment 'header'" in result.output

    def test_add_with_parent(self, runner, project):
        invoke(runner, project, ["init"])
        result = invoke(runner, project, ["add", "main.py", "all", "0", "10"])
        # Extract ID from output
        frag_id = result.output.split("(")[1].split(")")[0]
        result2 = invoke(runner, project, ["add", "main.py", "child", "2", "5", "--parent", frag_id])
        assert result2.exit_code == 0

    def test_add_with_prose(self, runner, project):
        invoke(runner, project, ["init"])
        result = invoke(runner, project, ["add", "main.py", "block", "0", "5", "--prose", "Explanation"])
        assert result.exit_code == 0

        store = FragmentStore(project)
        frag_id = result.output.split("(")[1].split(")")[0]
        frag = store.get_fragment("main.py", frag_id)
        assert frag.prose == "Explanation"

    def test_add_overlap_rejected(self, runner, project):
        invoke(runner, project, ["init"])
        invoke(runner, project, ["add", "main.py", "a", "0", "5"])
        result = invoke(runner, project, ["add", "main.py", "b", "3", "8"])
        assert result.exit_code == 1
        assert "overlaps" in result.output.lower() or "Error" in result.output

    def test_add_duplicate_name_rejected(self, runner, project):
        invoke(runner, project, ["init"])
        invoke(runner, project, ["add", "main.py", "block", "0", "3"])
        result = invoke(runner, project, ["add", "main.py", "block", "5", "8"])
        assert result.exit_code == 1


class TestAddInline:
    def test_add_inline(self, runner, project):
        invoke(runner, project, ["init"])
        result = invoke(runner, project, ["add-inline", "main.py", "expr", "3", "5", "15"])
        assert result.exit_code == 0
        assert "inline" in result.output.lower()


class TestRm:
    def test_rm_fragment(self, runner, project):
        invoke(runner, project, ["init"])
        result = invoke(runner, project, ["add", "main.py", "block", "0", "5"])
        frag_id = result.output.split("(")[1].split(")")[0]

        result2 = invoke(runner, project, ["rm", "main.py", frag_id])
        assert result2.exit_code == 0
        assert "Removed" in result2.output

    def test_rm_nonexistent(self, runner, project):
        invoke(runner, project, ["init"])
        # Need at least one fragment in the file for it to have entries
        invoke(runner, project, ["add", "main.py", "block", "0", "5"])
        result = invoke(runner, project, ["rm", "main.py", "nonexistent"])
        assert result.exit_code == 1


class TestRename:
    def test_rename(self, runner, project):
        invoke(runner, project, ["init"])
        result = invoke(runner, project, ["add", "main.py", "old", "0", "5"])
        frag_id = result.output.split("(")[1].split(")")[0]

        result2 = invoke(runner, project, ["rename", "main.py", frag_id, "new"])
        assert result2.exit_code == 0
        assert "new" in result2.output


class TestLs:
    def test_ls_empty(self, runner, project):
        invoke(runner, project, ["init"])
        result = invoke(runner, project, ["ls", "main.py"])
        assert "No fragments" in result.output

    def test_ls_tree(self, runner, project):
        invoke(runner, project, ["init"])
        result = invoke(runner, project, ["add", "main.py", "root", "0", "10"])
        root_id = result.output.split("(")[1].split(")")[0]
        invoke(runner, project, ["add", "main.py", "child1", "1", "4", "--parent", root_id])
        invoke(runner, project, ["add", "main.py", "child2", "5", "8", "--parent", root_id])

        result = invoke(runner, project, ["ls", "main.py"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert "root" in lines[0]
        assert "child1" in lines[1]
        assert lines[1].startswith("  ")  # indented
        assert "child2" in lines[2]


class TestCheck:
    def test_check_valid(self, runner, project):
        invoke(runner, project, ["init"])
        invoke(runner, project, ["add", "main.py", "block", "0", "5"])
        result = invoke(runner, project, ["check", "main.py"])
        assert result.exit_code == 0
        assert "OK" in result.output

    def test_check_no_fragments(self, runner, project):
        invoke(runner, project, ["init"])
        result = invoke(runner, project, ["check", "main.py"])
        assert result.exit_code == 0


class TestExpand:
    def test_expand(self, runner, project):
        invoke(runner, project, ["init"])
        result = invoke(runner, project, ["expand", "main.py"])
        assert result.exit_code == 0
        assert "line0" in result.output

    def test_expand_nonexistent(self, runner, project):
        invoke(runner, project, ["init"])
        result = invoke(runner, project, ["expand", "nope.py"])
        assert result.exit_code == 1


class TestAnchor:
    def test_anchor_no_change(self, runner, project):
        invoke(runner, project, ["init"])
        result = invoke(runner, project, ["add", "main.py", "block", "0", "5"])
        # Save cache
        store = FragmentStore(project)
        content = (project / "main.py").read_text()
        store.save_cache("main.py", content)

        result = invoke(runner, project, ["anchor", "main.py"])
        assert "up to date" in result.output

    def test_anchor_after_insert(self, runner, project):
        invoke(runner, project, ["init"])
        invoke(runner, project, ["add", "main.py", "block", "5", "8"])

        # Cache current content
        store = FragmentStore(project)
        content = (project / "main.py").read_text()
        store.save_cache("main.py", content)

        # Modify file: insert 2 lines at the beginning
        new_content = "new1\nnew2\n" + content
        (project / "main.py").write_text(new_content)

        result = invoke(runner, project, ["anchor", "main.py"])
        assert result.exit_code == 0
        assert "shifted" in result.output

        # Verify fragment shifted
        frag = store.get_fragment_by_name("main.py", "block")
        assert frag.range.start_line == 7  # 5 + 2
        assert frag.range.end_line == 10   # 8 + 2

    def test_anchor_no_cache(self, runner, project):
        invoke(runner, project, ["init"])
        invoke(runner, project, ["add", "main.py", "block", "0", "5"])

        # Modify file without cache
        (project / "main.py").write_text("changed\n")

        result = invoke(runner, project, ["anchor", "main.py"])
        assert "no cached content" in result.output


class TestRequireInit:
    def test_add_without_init(self, runner, project):
        result = invoke(runner, project, ["add", "main.py", "block", "0", "5"])
        assert result.exit_code == 1
        assert "init" in result.output.lower()
