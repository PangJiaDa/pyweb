"""Language → comment syntax mapping."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommentStyle:
    prefix: str   # e.g. "# " or "// " or "<!-- "
    suffix: str   # e.g. "" or " -->"

    def wrap(self, text: str) -> str:
        return f"{self.prefix}{text}{self.suffix}"


# Default styles by file extension
_DEFAULTS: dict[str, CommentStyle] = {
    ".py": CommentStyle("# ", ""),
    ".pyw": CommentStyle("# ", ""),
    ".rb": CommentStyle("# ", ""),
    ".sh": CommentStyle("# ", ""),
    ".bash": CommentStyle("# ", ""),
    ".zsh": CommentStyle("# ", ""),
    ".yaml": CommentStyle("# ", ""),
    ".yml": CommentStyle("# ", ""),
    ".toml": CommentStyle("# ", ""),
    ".r": CommentStyle("# ", ""),
    ".pl": CommentStyle("# ", ""),
    ".pm": CommentStyle("# ", ""),
    ".js": CommentStyle("// ", ""),
    ".jsx": CommentStyle("// ", ""),
    ".ts": CommentStyle("// ", ""),
    ".tsx": CommentStyle("// ", ""),
    ".java": CommentStyle("// ", ""),
    ".c": CommentStyle("// ", ""),
    ".h": CommentStyle("// ", ""),
    ".cpp": CommentStyle("// ", ""),
    ".hpp": CommentStyle("// ", ""),
    ".cs": CommentStyle("// ", ""),
    ".go": CommentStyle("// ", ""),
    ".rs": CommentStyle("// ", ""),
    ".swift": CommentStyle("// ", ""),
    ".kt": CommentStyle("// ", ""),
    ".scala": CommentStyle("// ", ""),
    ".dart": CommentStyle("// ", ""),
    ".php": CommentStyle("// ", ""),
    ".m": CommentStyle("// ", ""),
    ".zig": CommentStyle("// ", ""),
    ".v": CommentStyle("// ", ""),
    ".lua": CommentStyle("-- ", ""),
    ".hs": CommentStyle("-- ", ""),
    ".sql": CommentStyle("-- ", ""),
    ".ada": CommentStyle("-- ", ""),
    ".elm": CommentStyle("-- ", ""),
    ".html": CommentStyle("<!-- ", " -->"),
    ".xml": CommentStyle("<!-- ", " -->"),
    ".svg": CommentStyle("<!-- ", " -->"),
    ".vue": CommentStyle("<!-- ", " -->"),
    ".css": CommentStyle("/* ", " */"),
    ".scss": CommentStyle("/* ", " */"),
    ".less": CommentStyle("/* ", " */"),
    ".bat": CommentStyle("REM ", ""),
    ".cmd": CommentStyle("REM ", ""),
    ".ps1": CommentStyle("# ", ""),
    ".lisp": CommentStyle(";; ", ""),
    ".clj": CommentStyle(";; ", ""),
    ".scm": CommentStyle(";; ", ""),
    ".ex": CommentStyle("# ", ""),
    ".exs": CommentStyle("# ", ""),
    ".erl": CommentStyle("% ", ""),
    ".ml": CommentStyle("(* ", " *)"),
    ".mli": CommentStyle("(* ", " *)"),
    ".f90": CommentStyle("! ", ""),
    ".f": CommentStyle("! ", ""),
    ".nim": CommentStyle("# ", ""),
    ".cr": CommentStyle("# ", ""),
    ".jl": CommentStyle("# ", ""),
}


def get_comment_style(file_path: str, overrides: dict[str, dict] | None = None) -> CommentStyle:
    """Get the comment style for a file based on its extension.

    Args:
        file_path: Path to the source file.
        overrides: Optional dict of extension → {"prefix": ..., "suffix": ...}.
    """
    ext = Path(file_path).suffix.lower()

    if overrides and ext in overrides:
        o = overrides[ext]
        return CommentStyle(prefix=o.get("prefix", "# "), suffix=o.get("suffix", ""))

    if ext in _DEFAULTS:
        return _DEFAULTS[ext]

    # Fallback: hash comment
    return CommentStyle("# ", "")
