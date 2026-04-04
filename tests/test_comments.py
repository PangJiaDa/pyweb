"""Tests for configurable comment styles."""
import json
import subprocess
import pytest
from pathlib import Path

from pyweb.core.comments import get_comment_style, load_config_overrides, CommentStyle

PYTHON = "python3"


def run_pyweb(*args: str, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, "-m", "pyweb", "-p", cwd, *args],
        capture_output=True, text=True, timeout=10,
    )


class TestGetCommentStyle:
    def test_python(self):
        cs = get_comment_style("main.py")
        assert cs.prefix == "# "
        assert cs.suffix == ""

    def test_js(self):
        cs = get_comment_style("app.js")
        assert cs.prefix == "// "

    def test_html(self):
        cs = get_comment_style("index.html")
        assert cs.prefix == "<!-- "
        assert cs.suffix == " -->"

    def test_css(self):
        cs = get_comment_style("style.css")
        assert cs.prefix == "/* "
        assert cs.suffix == " */"

    def test_unknown_falls_back(self):
        cs = get_comment_style("file.xyz")
        assert cs.prefix == "# "

    def test_explicit_prefix_suffix_overrides_all(self):
        cs = get_comment_style("main.py", prefix="REM ", suffix="")
        assert cs.prefix == "REM "
        assert cs.suffix == ""

    def test_explicit_prefix_overrides_defaults(self):
        cs = get_comment_style("index.html", prefix="// ")
        assert cs.prefix == "// "
        assert cs.suffix == ""

    def test_overrides_dict(self):
        overrides = {".mcf": {"prefix": "# ", "suffix": ""}}
        cs = get_comment_style("commands.mcf", overrides=overrides)
        assert cs.prefix == "# "

    def test_overrides_beat_defaults(self):
        overrides = {".py": {"prefix": "// ", "suffix": ""}}
        cs = get_comment_style("main.py", overrides=overrides)
        assert cs.prefix == "// "

    def test_explicit_beats_overrides(self):
        overrides = {".py": {"prefix": "// ", "suffix": ""}}
        cs = get_comment_style("main.py", overrides=overrides, prefix="-- ")
        assert cs.prefix == "-- "

    def test_wrap(self):
        cs = CommentStyle("<!-- ", " -->")
        assert cs.wrap("hello") == "<!-- hello -->"


class TestLoadConfigOverrides:
    def test_no_config(self, tmp_path):
        result = load_config_overrides(tmp_path)
        assert result == {}

    def test_config_with_comments(self, tmp_path):
        config = {"comments": {".mcf": {"prefix": "# "}}}
        (tmp_path / ".pyweb.json").write_text(json.dumps(config))
        result = load_config_overrides(tmp_path)
        assert ".mcf" in result
        assert result[".mcf"]["prefix"] == "# "

    def test_config_without_comments_key(self, tmp_path):
        (tmp_path / ".pyweb.json").write_text('{"version": 1}')
        result = load_config_overrides(tmp_path)
        assert result == {}

    def test_malformed_json(self, tmp_path):
        (tmp_path / ".pyweb.json").write_text("not json")
        result = load_config_overrides(tmp_path)
        assert result == {}


@pytest.fixture
def project(tmp_path):
    (tmp_path / "main.py").write_text("line0\nline1\nline2\nline3\n")
    (tmp_path / "page.html").write_text("<div>\n  <p>hi</p>\n  <p>bye</p>\n</div>\n")
    (tmp_path / "commands.mcf").write_text("say hello\ntp @s ~ ~1 ~\ngive @s stone\n")
    return tmp_path


class TestCliCommentFlags:
    def test_add_html_uses_correct_style(self, project):
        result = run_pyweb("add", "page.html", "content", "0", "3", cwd=str(project))
        assert result.returncode == 0
        content = (project / "page.html").read_text()
        assert "<!-- @pyweb:start" in content
        assert "-->" in content

    def test_add_with_explicit_prefix_suffix(self, project):
        result = run_pyweb(
            "add", "commands.mcf", "greeting", "0", "1",
            "--comment-prefix", "# ",
            "--comment-suffix", "",
            cwd=str(project),
        )
        assert result.returncode == 0
        content = (project / "commands.mcf").read_text()
        assert "# @pyweb:start" in content

    def test_add_with_config_file(self, project):
        # .mcf is unknown, falls back to "# " — but with config it uses "//"
        config = {"comments": {".mcf": {"prefix": "// ", "suffix": ""}}}
        (project / ".pyweb.json").write_text(json.dumps(config))

        result = run_pyweb("add", "commands.mcf", "teleport", "1", "2", cwd=str(project))
        assert result.returncode == 0
        content = (project / "commands.mcf").read_text()
        assert "// @pyweb:start" in content

    def test_explicit_flag_beats_config(self, project):
        config = {"comments": {".mcf": {"prefix": "// ", "suffix": ""}}}
        (project / ".pyweb.json").write_text(json.dumps(config))

        result = run_pyweb(
            "add", "commands.mcf", "greeting", "0", "1",
            "--comment-prefix", "-- ",
            cwd=str(project),
        )
        assert result.returncode == 0
        content = (project / "commands.mcf").read_text()
        assert "-- @pyweb:start" in content

    def test_prose_respects_comment_style(self, project):
        result = run_pyweb("add", "page.html", "content", "0", "3", cwd=str(project))
        fid = result.stdout.split("(")[1].split(")")[0]

        result = run_pyweb("prose", "page.html", fid, "Navigation section", cwd=str(project))
        assert result.returncode == 0
        content = (project / "page.html").read_text()
        assert "<!-- @pyweb:prose Navigation section -->" in content

    def test_markers_parse_regardless_of_style(self, project):
        """Manually write markers in unusual style — parser should still find them."""
        (project / "weird.txt").write_text(
            'REM @pyweb:start id="w1" name="batch_block"\n'
            'echo hello\n'
            'REM @pyweb:end id="w1"\n'
        )
        result = run_pyweb("parse", "weird.txt", cwd=str(project))
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data["fragments"]) == 1
        assert data["fragments"][0]["name"] == "batch_block"
