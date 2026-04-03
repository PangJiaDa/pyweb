"""Import bridge: convert .pwb files to sidecar-based fragment structure.

Tangles the .pwb file to produce source output, then creates fragment
definitions in the sidecar matching the original chunk structure.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from dataclasses import dataclass

from pyweb.core.models import Range, Fragment, FileFragments, _new_id
from pyweb.core.store import FragmentStore

# Reuse the existing PyWeb parser
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from main import PyWeb, CodeFragment


@dataclass
class _ExpandedFragment:
    """Tracks where a fragment ends up in the tangled output."""
    name: str
    start_line: int
    end_line: int  # exclusive
    children: list[str]  # child fragment names


def import_pwb(
    pwb_path: Path,
    output_path: Path,
    project_root: Path,
    top_level_fragment: str = "*",
) -> None:
    """Import a .pwb file: tangle it, write the output, create sidecar fragments.

    Args:
        pwb_path: Path to the .pwb source file.
        output_path: Path where the tangled output should be written.
        project_root: Root of the project (where .pyweb/ lives).
        top_level_fragment: Name of the root fragment to expand.
    """
    # Parse and tangle
    pyweb = PyWeb(pwb_path)
    tangled = pyweb.tangle(root_fragment=top_level_fragment, include_source_lineno=False)

    # Write tangled output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(tangled)

    # Build a source map by re-expanding with line tracking
    line_map = _build_line_map(pyweb, top_level_fragment)

    # Create sidecar fragments
    store = FragmentStore(project_root)
    if not store.is_initialized():
        store.init()

    rel_path = str(output_path.relative_to(project_root))
    content = output_path.read_text()

    ff = FileFragments(
        file=rel_path,
        content_hash=store.content_hash(content),
        fragments=[],
    )

    # Create Fragment objects from the line map
    id_by_name: dict[str, str] = {}
    for ef in line_map:
        fid = _new_id()
        id_by_name[ef.name] = fid

    for ef in line_map:
        frag = Fragment(
            id=id_by_name[ef.name],
            name=ef.name,
            file=rel_path,
            range=Range(ef.start_line, 0, ef.end_line, 0),
            children=[id_by_name[c] for c in ef.children if c in id_by_name],
            prose=None,
        )
        ff.fragments.append(frag)

    store.save_file(ff)
    store.save_cache(rel_path, content)


def _build_line_map(pyweb: PyWeb, root_fragment: str) -> list[_ExpandedFragment]:
    """Re-expand the fragment tree, tracking line positions in the output.

    Returns a list of _ExpandedFragment with start/end line positions.
    """
    # We need to do a simplified expansion that tracks line positions.
    # Strategy: expand the root fragment recursively, tracking current line number.
    result: list[_ExpandedFragment] = []
    _expand_recursive(pyweb, root_fragment, 0, "", result)
    return result


def _expand_recursive(
    pyweb: PyWeb,
    frag_name: str,
    start_line: int,
    indentation: str,
    result: list[_ExpandedFragment],
) -> int:
    """Recursively expand a fragment, tracking line positions.

    Returns the next available line number after this fragment.
    """
    if frag_name not in pyweb.fragment_map:
        return start_line

    frags = pyweb.fragment_map[frag_name]
    current_line = start_line
    children: list[str] = []

    multiline_ref_re = PyWeb.CODE_FRAGMENT_MULTILINE_REFERENCE_RE

    for code_frag in frags:
        for code_line in code_frag.code_lines:
            # Check if this line is a reference to another fragment
            match = multiline_ref_re.match(code_line.strip())
            if match:
                child_name = match.group("fragment_name")
                child_indent = indentation + match.group("leading_whitespace")
                children.append(child_name)
                current_line = _expand_recursive(
                    pyweb, child_name, current_line, child_indent, result
                )
            else:
                current_line += 1

    ef = _ExpandedFragment(
        name=frag_name,
        start_line=start_line,
        end_line=current_line,
        children=children,
    )
    result.append(ef)
    return current_line
