from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from pyweb.core.comments import get_comment_style
from pyweb.core.parser import parse_markers, get_roots, get_fragment_by_id, get_fragment_by_name
from pyweb.core import writer


def _project_root(ctx: click.Context) -> Path:
    return Path(ctx.obj or ".").resolve()


def _read_source(project_root: Path, file_path: str) -> str:
    p = project_root / file_path
    if not p.exists():
        click.echo(f"Error: file '{file_path}' not found.", err=True)
        sys.exit(1)
    return p.read_text()


def _write_source(project_root: Path, file_path: str, content: str) -> None:
    p = project_root / file_path
    p.write_text(content)


@click.group()
@click.option("--project", "-p", default=".", help="Project root directory.")
@click.pass_context
def cli(ctx: click.Context, project: str) -> None:
    """pyweb — hierarchical code fragment overlay."""
    ctx.ensure_object(dict)
    ctx.obj = project


@cli.command()
@click.argument("file")
@click.argument("name")
@click.argument("start_line", type=int)
@click.argument("end_line", type=int)
@click.option("--prose", default=None, help="Prose/explanation for this fragment.")
@click.pass_context
def add(ctx: click.Context, file: str, name: str, start_line: int, end_line: int,
        prose: str | None) -> None:
    """Define a new fragment by inserting markers around a line range."""
    root = _project_root(ctx)
    source = _read_source(root, file)
    cs = get_comment_style(file)

    try:
        new_source, fid = writer.add_fragment(source, file, name, start_line, end_line, cs, prose)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    _write_source(root, file, new_source)
    click.echo(f"Created fragment '{name}' ({fid}) [{start_line} - {end_line}]")


@cli.command()
@click.argument("file")
@click.argument("fragment_id")
@click.pass_context
def rm(ctx: click.Context, file: str, fragment_id: str) -> None:
    """Remove a fragment's markers (code stays in source)."""
    root = _project_root(ctx)
    source = _read_source(root, file)

    try:
        new_source = writer.remove_fragment(source, fragment_id)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    _write_source(root, file, new_source)
    click.echo(f"Removed fragment {fragment_id}")


@cli.command()
@click.argument("file")
@click.argument("fragment_id")
@click.argument("new_name")
@click.pass_context
def rename(ctx: click.Context, file: str, fragment_id: str, new_name: str) -> None:
    """Rename a fragment."""
    root = _project_root(ctx)
    source = _read_source(root, file)

    try:
        new_source = writer.rename_fragment(source, fragment_id, new_name)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    _write_source(root, file, new_source)
    click.echo(f"Renamed fragment {fragment_id} → '{new_name}'")


@cli.command()
@click.argument("file")
@click.argument("fragment_id")
@click.argument("text", required=False, default=None)
@click.pass_context
def prose(ctx: click.Context, file: str, fragment_id: str, text: str | None) -> None:
    """Set or clear prose for a fragment."""
    root = _project_root(ctx)
    source = _read_source(root, file)
    cs = get_comment_style(file)

    try:
        new_source = writer.set_prose(source, file, fragment_id, text, cs)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    _write_source(root, file, new_source)
    if text:
        click.echo(f"Set prose on {fragment_id}")
    else:
        click.echo(f"Cleared prose on {fragment_id}")


@cli.command()
@click.argument("file")
@click.argument("fragment_id")
@click.argument("start_line", type=int)
@click.argument("end_line", type=int)
@click.pass_context
def resize(ctx: click.Context, file: str, fragment_id: str, start_line: int, end_line: int) -> None:
    """Resize a fragment to a new line range."""
    root = _project_root(ctx)
    source = _read_source(root, file)
    cs = get_comment_style(file)

    try:
        new_source = writer.resize_fragment(source, file, fragment_id, start_line, end_line, cs)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    _write_source(root, file, new_source)
    click.echo(f"Resized fragment {fragment_id} → [{start_line} - {end_line}]")


@cli.command()
@click.argument("file")
@click.pass_context
def ls(ctx: click.Context, file: str) -> None:
    """List fragments as an indented tree."""
    root = _project_root(ctx)
    source = _read_source(root, file)
    result = parse_markers(source, file)

    if not result.fragments:
        click.echo("No fragments in this file.")
        return

    by_id = {f.id: f for f in result.fragments}
    roots = get_roots(result.fragments)

    def print_tree(frag_id: str, depth: int) -> None:
        f = by_id[frag_id]
        indent = "  " * depth
        prose_hint = " *" if f.prose else ""
        click.echo(f"{indent}{f.name} ({f.id}) [{f.start_line} - {f.end_line}]{prose_hint}")
        for cid in f.children:
            if cid in by_id:
                print_tree(cid, depth + 1)

    for r in roots:
        print_tree(r.id, 0)


@cli.command()
@click.argument("file")
@click.option("--fragment", "-f", default=None, help="Show only this fragment (ID or name).")
@click.pass_context
def view(ctx: click.Context, file: str, fragment: str | None) -> None:
    """Print hierarchical view to stdout."""
    root = _project_root(ctx)
    source = _read_source(root, file)
    lines = source.splitlines(keepends=True)
    result = parse_markers(source, file)

    if not result.fragments:
        click.echo("No fragments in this file.")
        return

    by_id = {f.id: f for f in result.fragments}
    frags_to_show: list = []

    if fragment:
        f = get_fragment_by_id(result.fragments, fragment)
        if f is None:
            f = get_fragment_by_name(result.fragments, fragment)
        if f is None:
            click.echo(f"Fragment '{fragment}' not found.", err=True)
            sys.exit(1)
        frags_to_show = [f]
    else:
        frags_to_show = get_roots(result.fragments)

    def render(frag, depth: int) -> None:
        if depth == 0:
            click.echo(f"=== {frag.name} ===")
        else:
            click.echo(f"--- {frag.name} ---")

        if frag.prose:
            click.echo(frag.prose)
            click.echo()

        # Print code lines, rendering children inline
        child_frags = [by_id[cid] for cid in frag.children if cid in by_id]
        child_frags.sort(key=lambda c: c.start_line)

        line_idx = frag.content_start_line
        for child in child_frags:
            # Print owned lines before this child
            for i in range(line_idx, child.start_line):
                if i < len(lines):
                    click.echo(lines[i], nl=False)
            render(child, depth + 1)
            line_idx = child.end_line

        # Print owned lines after last child
        for i in range(line_idx, frag.content_end_line):
            if i < len(lines):
                click.echo(lines[i], nl=False)

    for f in frags_to_show:
        render(f, 0)


@cli.command()
@click.argument("file")
@click.pass_context
def expand(ctx: click.Context, file: str) -> None:
    """Print the source file (expanded view)."""
    root = _project_root(ctx)
    source = _read_source(root, file)
    click.echo(source, nl=False)


@cli.command()
@click.argument("file")
@click.pass_context
def parse(ctx: click.Context, file: str) -> None:
    """Parse markers and output fragment tree as JSON (for editor extensions)."""
    root = _project_root(ctx)
    source = _read_source(root, file)
    result = parse_markers(source, file)

    data = {
        "file": file,
        "fragments": [
            {
                "id": f.id,
                "name": f.name,
                "start_line": f.start_line,
                "end_line": f.end_line,
                "content_start_line": f.content_start_line,
                "content_end_line": f.content_end_line,
                "children": f.children,
                "parent_id": f.parent_id,
                "prose": f.prose,
            }
            for f in result.fragments
        ],
        "warnings": [
            {"line": w.line, "message": w.message}
            for w in result.warnings
        ],
    }
    click.echo(json.dumps(data, indent=2))


@cli.command()
@click.argument("file")
@click.pass_context
def check(ctx: click.Context, file: str) -> None:
    """Validate fragment markers in a file."""
    root = _project_root(ctx)
    source = _read_source(root, file)
    result = parse_markers(source, file)

    if result.warnings:
        for w in result.warnings:
            click.echo(f"  WARNING (line {w.line}): {w.message}", err=True)
        sys.exit(1)
    else:
        click.echo("OK — no warnings.")
