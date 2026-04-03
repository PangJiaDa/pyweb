"""Integration tests: run the actual CLI binary end-to-end.

These tests shell out to `python3 -m pyweb` — the same path the VS Code
extension uses.
"""
import json
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

    def test_add_fragment(self, project):
        result = run_pyweb("add", "main.py", "header", "0", "3", cwd=str(project))
        assert result.returncode == 0
        assert "Created fragment" in result.stdout
        # Markers should be in the file
        content = (project / "main.py").read_text()
        assert "@pyweb:start" in content
        assert "@pyweb:end" in content
        assert 'name="header"' in content

    def test_add_with_prose(self, project):
        result = run_pyweb("add", "main.py", "block", "0", "3", "--prose", "Explanation", cwd=str(project))
        assert result.returncode == 0
        content = (project / "main.py").read_text()
        assert "@pyweb:prose Explanation" in content

    def test_ls(self, project):
        run_pyweb("add", "main.py", "header", "0", "3", cwd=str(project))
        result = run_pyweb("ls", "main.py", cwd=str(project))
        assert result.returncode == 0
        assert "header" in result.stdout

    def test_ls_empty(self, project):
        result = run_pyweb("ls", "main.py", cwd=str(project))
        assert result.returncode == 0
        assert "No fragments" in result.stdout

    def test_rm(self, project):
        result = run_pyweb("add", "main.py", "block", "1", "4", cwd=str(project))
        fid = result.stdout.split("(")[1].split(")")[0]

        result = run_pyweb("rm", "main.py", fid, cwd=str(project))
        assert result.returncode == 0
        assert "Removed" in result.stdout

        content = (project / "main.py").read_text()
        assert "@pyweb" not in content
        assert "line1" in content  # code preserved

    def test_rename(self, project):
        result = run_pyweb("add", "main.py", "old_name", "0", "3", cwd=str(project))
        fid = result.stdout.split("(")[1].split(")")[0]

        result = run_pyweb("rename", "main.py", fid, "new_name", cwd=str(project))
        assert result.returncode == 0
        assert "new_name" in result.stdout

        content = (project / "main.py").read_text()
        assert 'name="new_name"' in content
        assert 'name="old_name"' not in content

    def test_prose_set_and_clear(self, project):
        result = run_pyweb("add", "main.py", "block", "0", "3", cwd=str(project))
        fid = result.stdout.split("(")[1].split(")")[0]

        # Set prose
        result = run_pyweb("prose", "main.py", fid, "New note", cwd=str(project))
        assert result.returncode == 0
        content = (project / "main.py").read_text()
        assert "@pyweb:prose New note" in content

        # Clear prose
        result = run_pyweb("prose", "main.py", fid, cwd=str(project))
        assert result.returncode == 0
        content = (project / "main.py").read_text()
        assert "@pyweb:prose" not in content

    def test_view(self, project):
        run_pyweb("add", "main.py", "header", "0", "3", cwd=str(project))
        result = run_pyweb("view", "main.py", cwd=str(project))
        assert result.returncode == 0
        assert "=== header ===" in result.stdout

    def test_view_specific_fragment(self, project):
        run_pyweb("add", "main.py", "header", "0", "3", cwd=str(project))
        run_pyweb("add", "main.py", "body", "6", "9", cwd=str(project))
        result = run_pyweb("view", "main.py", "-f", "header", cwd=str(project))
        assert result.returncode == 0
        assert "header" in result.stdout

    def test_expand(self, project):
        run_pyweb("add", "main.py", "block", "0", "3", cwd=str(project))
        result = run_pyweb("expand", "main.py", cwd=str(project))
        assert result.returncode == 0
        assert "@pyweb:start" in result.stdout  # markers are in the file
        assert "line0" in result.stdout

    def test_parse_json(self, project):
        run_pyweb("add", "main.py", "block", "1", "4", cwd=str(project))
        result = run_pyweb("parse", "main.py", cwd=str(project))
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["file"] == "main.py"
        assert len(data["fragments"]) == 1
        assert data["fragments"][0]["name"] == "block"
        assert data["warnings"] == []

    def test_check_clean(self, project):
        run_pyweb("add", "main.py", "block", "0", "3", cwd=str(project))
        result = run_pyweb("check", "main.py", cwd=str(project))
        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_check_with_warnings(self, project):
        # Manually write a broken marker
        (project / "main.py").write_text(
            '# @pyweb:start id="f1" name="broken"\n'
            'x = 1\n'
            # missing end marker
        )
        result = run_pyweb("check", "main.py", cwd=str(project))
        assert result.returncode == 1
        assert "WARNING" in result.stdout or "WARNING" in result.stderr

    def test_resize(self, project):
        result = run_pyweb("add", "main.py", "block", "2", "5", cwd=str(project))
        fid = result.stdout.split("(")[1].split(")")[0]

        result = run_pyweb("resize", "main.py", fid, "1", "7", cwd=str(project))
        assert result.returncode == 0
        assert "Resized" in result.stdout

    def test_nested_fragments(self, project):
        # Add parent covering all lines
        run_pyweb("add", "main.py", "parent", "0", "10", cwd=str(project))
        # Now add child inside (lines shifted by parent markers)
        run_pyweb("add", "main.py", "child", "3", "6", cwd=str(project))

        result = run_pyweb("parse", "main.py", cwd=str(project))
        data = json.loads(result.stdout)
        assert len(data["fragments"]) == 2

        parent = [f for f in data["fragments"] if f["name"] == "parent"][0]
        child = [f for f in data["fragments"] if f["name"] == "child"][0]
        assert child["parent_id"] == parent["id"]

    def test_error_on_missing_file(self, project):
        result = run_pyweb("add", "nope.py", "block", "0", "3", cwd=str(project))
        assert result.returncode == 1

    def test_full_workflow(self, project):
        """End-to-end: add fragments, nested, view, check, remove."""
        cwd = str(project)

        # Add parent
        r = run_pyweb("add", "main.py", "all", "0", "10", cwd=cwd)
        assert r.returncode == 0

        # Add children (lines shifted after parent markers inserted)
        r = run_pyweb("add", "main.py", "header", "2", "5", cwd=cwd)
        assert r.returncode == 0
        header_id = r.stdout.split("(")[1].split(")")[0]

        r = run_pyweb("add", "main.py", "body", "7", "10", cwd=cwd)
        assert r.returncode == 0

        # Add prose
        r = run_pyweb("prose", "main.py", header_id, "The header section", cwd=cwd)
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
        assert "--- header ---" in r.stdout

        # Parse JSON
        r = run_pyweb("parse", "main.py", cwd=cwd)
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert len(data["fragments"]) == 3

        # Check
        r = run_pyweb("check", "main.py", cwd=cwd)
        assert r.returncode == 0

        # Rename
        r = run_pyweb("rename", "main.py", header_id, "top_section", cwd=cwd)
        assert r.returncode == 0

        # Remove one fragment
        r = run_pyweb("rm", "main.py", header_id, cwd=cwd)
        assert r.returncode == 0

        # Should still have 2 fragments
        r = run_pyweb("parse", "main.py", cwd=cwd)
        data = json.loads(r.stdout)
        assert len(data["fragments"]) == 2
