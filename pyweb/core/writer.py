"""Insert, remove, and modify @pyweb markers in source files."""
from __future__ import annotations

from pyweb.core.comments import CommentStyle, get_comment_style
from pyweb.core.parser import parse_markers, get_fragment_by_id, ParsedFragment
from pyweb.core.models import _new_id


def add_fragment(
    source: str,
    file_path: str,
    name: str,
    start_line: int,
    end_line: int,
    comment_style: CommentStyle | None = None,
    prose: str | None = None,
) -> tuple[str, str]:
    """Insert start/end markers around a line range.

    Returns (new_source, fragment_id).
    start_line and end_line are 0-indexed. end_line is exclusive.
    Markers are inserted so that start_line content is inside the fragment.
    """
    if comment_style is None:
        comment_style = get_comment_style(file_path)

    fid = _new_id()
    lines = source.splitlines(keepends=True)

    # Detect indentation from the first line of the selection
    indent = ""
    if start_line < len(lines):
        content = lines[start_line]
        indent = content[: len(content) - len(content.lstrip())]

    start_marker = indent + comment_style.wrap(f'@pyweb:start id="{fid}" name="{name}"') + "\n"

    prose_lines: list[str] = []
    if prose:
        for pl in prose.split("\n"):
            prose_lines.append(indent + comment_style.wrap(f"@pyweb:prose {pl}") + "\n")

    end_marker = indent + comment_style.wrap(f'@pyweb:end id="{fid}"') + "\n"

    new_lines = (
        lines[:start_line]
        + [start_marker]
        + prose_lines
        + lines[start_line:end_line]
        + [end_marker]
        + lines[end_line:]
    )

    return "".join(new_lines), fid


def remove_fragment(source: str, fragment_id: str) -> str:
    """Remove all markers (start, prose, end) for a fragment. Keeps the code."""
    result = parse_markers(source)
    frag = get_fragment_by_id(result.fragments, fragment_id)
    if frag is None:
        raise ValueError(f"Fragment '{fragment_id}' not found")

    lines = source.splitlines(keepends=True)

    # Collect line numbers to remove (markers and prose)
    remove_lines: set[int] = set()
    remove_lines.add(frag.start_line)

    # Prose lines are between start_line and content_start_line
    for i in range(frag.start_line + 1, frag.content_start_line):
        remove_lines.add(i)

    if frag.end_line > 0:
        # end_line is exclusive, so the actual end marker is at end_line - 1
        remove_lines.add(frag.end_line - 1)

    new_lines = [ln for i, ln in enumerate(lines) if i not in remove_lines]
    return "".join(new_lines)


def rename_fragment(source: str, fragment_id: str, new_name: str) -> str:
    """Change the name in a fragment's start marker."""
    result = parse_markers(source)
    frag = get_fragment_by_id(result.fragments, fragment_id)
    if frag is None:
        raise ValueError(f"Fragment '{fragment_id}' not found")

    lines = source.splitlines(keepends=True)
    old_line = lines[frag.start_line]

    # Replace name="old" with name="new"
    import re
    new_line = re.sub(r'name="[^"]*"', f'name="{new_name}"', old_line)
    lines[frag.start_line] = new_line

    return "".join(lines)


def set_prose(
    source: str,
    file_path: str,
    fragment_id: str,
    prose: str | None,
    comment_style: CommentStyle | None = None,
) -> str:
    """Set or replace prose for a fragment."""
    if comment_style is None:
        comment_style = get_comment_style(file_path)

    result = parse_markers(source)
    frag = get_fragment_by_id(result.fragments, fragment_id)
    if frag is None:
        raise ValueError(f"Fragment '{fragment_id}' not found")

    lines = source.splitlines(keepends=True)

    # Detect indentation from start marker
    start_content = lines[frag.start_line]
    indent = start_content[: len(start_content) - len(start_content.lstrip())]

    # Remove existing prose lines
    old_prose_lines: set[int] = set()
    for i in range(frag.start_line + 1, frag.content_start_line):
        old_prose_lines.add(i)

    filtered = [ln for i, ln in enumerate(lines) if i not in old_prose_lines]

    if prose:
        # Insert new prose after start marker
        # Find where start marker is in filtered list
        insert_at = frag.start_line + 1 - 0  # offset from removed lines above start is 0
        new_prose_lines = []
        for pl in prose.split("\n"):
            new_prose_lines.append(indent + comment_style.wrap(f"@pyweb:prose {pl}") + "\n")
        filtered = filtered[:insert_at] + new_prose_lines + filtered[insert_at:]

    return "".join(filtered)


def resize_fragment(
    source: str,
    file_path: str,
    fragment_id: str,
    new_start_line: int,
    new_end_line: int,
    comment_style: CommentStyle | None = None,
) -> str:
    """Move a fragment's start/end markers to new positions.

    new_start_line/new_end_line are the desired content boundaries (0-indexed, end exclusive).
    The markers will be placed around this range.
    """
    if comment_style is None:
        comment_style = get_comment_style(file_path)

    result = parse_markers(source)
    frag = get_fragment_by_id(result.fragments, fragment_id)
    if frag is None:
        raise ValueError(f"Fragment '{fragment_id}' not found")

    # Step 1: Remove old markers
    source_no_markers = remove_fragment(source, fragment_id)

    # Step 2: Re-parse to get clean line numbers
    # But we need to account for line shifts from removing markers.
    # Simpler: just re-add at the new positions.
    # The positions need adjustment for removed lines above them.
    lines_removed_before_start = 0
    lines_removed_before_end = 0

    old_lines = source.splitlines(keepends=True)
    remove_set: set[int] = {frag.start_line}
    for i in range(frag.start_line + 1, frag.content_start_line):
        remove_set.add(i)
    if frag.end_line > 0:
        remove_set.add(frag.end_line - 1)

    for rl in sorted(remove_set):
        if rl < new_start_line:
            lines_removed_before_start += 1
        if rl < new_end_line:
            lines_removed_before_end += 1

    adj_start = new_start_line - lines_removed_before_start
    adj_end = new_end_line - lines_removed_before_end

    # Step 3: Re-add markers at adjusted positions
    new_source, _ = add_fragment(
        source_no_markers, file_path, frag.name,
        adj_start, adj_end, comment_style, frag.prose,
    )

    # Fix the ID to keep the original
    new_source = new_source.replace(
        new_source.split('@pyweb:start id="')[1].split('"')[0] if '@pyweb:start' in new_source else "",
        "",  # this approach is fragile
    )

    # Actually, let's do this more carefully: remove, then re-insert with original ID
    return _add_fragment_with_id(
        source_no_markers, file_path, frag.id, frag.name,
        adj_start, adj_end, comment_style, frag.prose,
    )


def _add_fragment_with_id(
    source: str,
    file_path: str,
    fid: str,
    name: str,
    start_line: int,
    end_line: int,
    comment_style: CommentStyle,
    prose: str | None = None,
) -> str:
    """Insert markers with a specific ID (used by resize to preserve ID)."""
    lines = source.splitlines(keepends=True)

    indent = ""
    if start_line < len(lines):
        content = lines[start_line]
        indent = content[: len(content) - len(content.lstrip())]

    start_marker = indent + comment_style.wrap(f'@pyweb:start id="{fid}" name="{name}"') + "\n"

    prose_lines: list[str] = []
    if prose:
        for pl in prose.split("\n"):
            prose_lines.append(indent + comment_style.wrap(f"@pyweb:prose {pl}") + "\n")

    end_marker = indent + comment_style.wrap(f'@pyweb:end id="{fid}"') + "\n"

    new_lines = (
        lines[:start_line]
        + [start_marker]
        + prose_lines
        + lines[start_line:end_line]
        + [end_marker]
        + lines[end_line:]
    )

    return "".join(new_lines)
