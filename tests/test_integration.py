"""Integration tests: run the actual CLI binary end-to-end.

These tests shell out to `python3 -m pyweb` — the same path the VS Code
extension uses. Catches issues like missing __main__.py that unit tests miss.
"""
import subprocess
import pytest
from pathlib import Path

PYTHON = "python3"


def run_pyweb(*args: str, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, "-m", "pyweb", "-p", cwd, *args],
        capture_output=True, text=True, timeout=10,
    )


@pytest.fixture
def project(tmp_path):
    src = tmp_path / "main.py"
    src.write_text("line0\nline1\nline2\nline3\nline4\nline5\nline6\nline7\nline8\nline9\n")
    return tmp_path


class TestCliEntryPoint:
    def test_help(self):
        result = subprocess.run(
            [PYTHON, "-m", "pyweb", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "pyweb" in result.stdout
        assert "init" in result.stdout

    def test_init_creates_pyweb_dir(self, project):
        result = run_pyweb("init", cwd=str(project))
        assert result.returncode == 0
        assert "Initialized" in result.stdout
        assert (project / ".pyweb").is_dir()
        assert (project / ".pyweb" / "config.json").exists()
        assert (project / ".pyweb" / "fragments").is_dir()

    def test_add_fragment(self, project):
        run_pyweb("init", cwd=str(project))
        result = run_pyweb("add", "main.py", "header", "0", "3", cwd=str(project))
        assert result.returncode == 0
        assert "Created fragment" in result.stdout

    def test_ls_shows_fragment(self, project):
        run_pyweb("init", cwd=str(project))
        run_pyweb("add", "main.py", "header", "0", "3", cwd=str(project))
        result = run_pyweb("ls", "main.py", cwd=str(project))
        assert result.returncode == 0
        assert "header" in result.stdout

    def test_add_and_remove(self, project):
        run_pyweb("init", cwd=str(project))
        result = run_pyweb("add", "main.py", "block", "0", "5", cwd=str(project))
        # Extract ID
        frag_id = result.stdout.split("(")[1].split(")")[0]

        result = run_pyweb("rm", "main.py", frag_id, cwd=str(project))
        assert result.returncode == 0
        assert "Removed" in result.stdout

    def test_view(self, project):
        run_pyweb("init", cwd=str(project))
        run_pyweb("add", "main.py", "header", "0", "3", cwd=str(project))
        result = run_pyweb("view", "main.py", cwd=str(project))
        assert result.returncode == 0
        assert "header" in result.stdout

    def test_expand(self, project):
        run_pyweb("init", cwd=str(project))
        result = run_pyweb("expand", "main.py", cwd=str(project))
        assert result.returncode == 0
        assert "line0" in result.stdout

    def test_check(self, project):
        run_pyweb("init", cwd=str(project))
        run_pyweb("add", "main.py", "block", "0", "5", cwd=str(project))
        result = run_pyweb("check", "main.py", cwd=str(project))
        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_anchor(self, project):
        run_pyweb("init", cwd=str(project))
        run_pyweb("add", "main.py", "block", "5", "8", cwd=str(project))

        # Cache current content
        src = project / "main.py"
        cache_dir = project / ".pyweb" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "main.py").write_text(src.read_text())

        # Modify file
        old = src.read_text()
        src.write_text("NEW\n" + old)

        result = run_pyweb("anchor", "main.py", cwd=str(project))
        assert result.returncode == 0
        assert "shifted" in result.stdout

    def test_rename(self, project):
        run_pyweb("init", cwd=str(project))
        result = run_pyweb("add", "main.py", "old_name", "0", "5", cwd=str(project))
        frag_id = result.stdout.split("(")[1].split(")")[0]

        result = run_pyweb("rename", "main.py", frag_id, "new_name", cwd=str(project))
        assert result.returncode == 0
        assert "new_name" in result.stdout

    def test_add_with_parent(self, project):
        run_pyweb("init", cwd=str(project))
        result = run_pyweb("add", "main.py", "parent", "0", "10", cwd=str(project))
        parent_id = result.stdout.split("(")[1].split(")")[0]

        result = run_pyweb("add", "main.py", "child", "2", "5", "--parent", parent_id, cwd=str(project))
        assert result.returncode == 0
        assert "Created fragment" in result.stdout

    def test_error_exits_nonzero(self, project):
        """Commands that fail should exit 1, not silently succeed."""
        # add without init
        result = run_pyweb("add", "main.py", "block", "0", "5", cwd=str(project))
        assert result.returncode == 1

    def test_full_workflow(self, project):
        """End-to-end: init, add fragments, view, anchor, check."""
        cwd = str(project)

        # Init
        r = run_pyweb("init", cwd=cwd)
        assert r.returncode == 0

        # Add parent
        r = run_pyweb("add", "main.py", "all", "0", "10", cwd=cwd)
        assert r.returncode == 0
        parent_id = r.stdout.split("(")[1].split(")")[0]

        # Add children
        r = run_pyweb("add", "main.py", "header", "0", "3", "--parent", parent_id, cwd=cwd)
        assert r.returncode == 0

        r = run_pyweb("add", "main.py", "body", "5", "8", "--parent", parent_id, cwd=cwd)
        assert r.returncode == 0

        # List
        r = run_pyweb("ls", "main.py", cwd=cwd)
        assert r.returncode == 0
        assert "all" in r.stdout
        assert "header" in r.stdout
        assert "body" in r.stdout

        # View
        r = run_pyweb("view", "main.py", cwd=cwd)
        assert r.returncode == 0
        assert "=== all ===" in r.stdout

        # Check
        r = run_pyweb("check", "main.py", cwd=cwd)
        assert r.returncode == 0
        assert "OK" in r.stdout
