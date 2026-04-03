"""Tests for the .pwb import bridge."""
import pytest
from pathlib import Path

from pyweb.core.store import FragmentStore
from pyweb.core.importer import import_pwb


@pytest.fixture
def project(tmp_path):
    store = FragmentStore(tmp_path)
    store.init()
    return tmp_path, store


class TestImportPwb:
    def test_simple_multiline(self, project):
        root, store = project
        pwb = root / "prog.pwb"
        pwb.write_text(
            "@ Top level\n"
            "\n"
            "@<*@>=\n"
            "x = 1\n"
            "y = 2\n"
            "print(x + y)\n"
        )
        output = root / "prog.py"
        import_pwb(pwb, output, root)

        # Output file should exist and contain tangled code
        assert output.exists()
        content = output.read_text()
        assert "x = 1" in content
        assert "y = 2" in content

        # Fragments should be created
        ff = store.load_file("prog.py")
        assert ff is not None
        assert len(ff.fragments) >= 1

    def test_nested_fragments(self, project):
        root, store = project
        pwb = root / "nested.pwb"
        pwb.write_text(
            "@<*@>=\n"
            "x = 6\n"
            "if x <= 5:\n"
            "    @<true block@>\n"
            "else:\n"
            "    @<false block@>\n"
            "\n"
            "@<true block@>=\n"
            "print('yes')\n"
            "\n"
            "@<false block@>=\n"
            "print('no')\n"
        )
        output = root / "nested.py"
        import_pwb(pwb, output, root)

        content = output.read_text()
        assert "print('yes')" in content
        assert "print('no')" in content

        ff = store.load_file("nested.py")
        assert ff is not None
        # Should have at least 3 fragments: *, true block, false block
        names = {f.name for f in ff.fragments}
        assert "true block" in names
        assert "false block" in names
        assert "*" in names

    def test_import_existing_example(self, project):
        """Import the actual test1.pwb from the examples directory."""
        root, store = project
        examples_dir = Path(__file__).resolve().parent.parent / "examples"
        pwb_path = examples_dir / "test1.pwb"
        if not pwb_path.exists():
            pytest.skip("examples/test1.pwb not found")

        output = root / "test1.py"
        import_pwb(pwb_path, output, root, top_level_fragment="*")

        assert output.exists()
        content = output.read_text()
        assert "print('hi')" in content

        ff = store.load_file("test1.py")
        assert ff is not None
        assert len(ff.fragments) > 0

    def test_cache_created(self, project):
        root, store = project
        pwb = root / "prog.pwb"
        pwb.write_text(
            "@<*@>=\n"
            "hello = 'world'\n"
        )
        output = root / "prog.py"
        import_pwb(pwb, output, root)

        cached = store.load_cache("prog.py")
        assert cached is not None
        assert cached == output.read_text()

    def test_output_in_subdir(self, project):
        root, store = project
        pwb = root / "prog.pwb"
        pwb.write_text("@<*@>=\nx = 1\n")
        output = root / "src" / "prog.py"
        import_pwb(pwb, output, root)

        assert output.exists()
        ff = store.load_file("src/prog.py")
        assert ff is not None
