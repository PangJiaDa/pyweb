from __future__ import annotations

import sys
from pathlib import Path

import click

from pyweb.core.models import Range
from pyweb.core.store import FragmentStore, ValidationError
from pyweb.core.anchorer import DiffAnchorer
from pyweb.core.sync import SyncEngine


def _get_store(ctx: click.Context) -> FragmentStore:
    project_root = Path(ctx.obj or ".").resolve()
    return FragmentStore(project_root)


def _require_init(store: FragmentStore) -> None:
    if not store.is_initialized():
        click.echo("Error: not a pyweb project. Run 'pyweb init' first.", err=True)
        sys.exit(1)


@click.group()
@click.option("--project", "-p", default=".", help="Project root directory.")
@click.pass_context
def cli(ctx: click.Context, project: str) -> None:
    """pyweb — hierarchical code fragment overlay."""
    ctx.ensure_object(dict)
    ctx.obj = project


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize .pyweb/ in current directory."""
    store = _get_store(ctx)
    store.init()
    click.echo("Initialized .pyweb/")

    # Add .pyweb/cache/ to .gitignore if not already there
    gitignore = store.project_root / ".gitignore"
    lines: list[str] = []
    if gitignore.exists():
        lines = gitignore.read_text().splitlines()
    if ".pyweb/cache/" not in lines:
        lines.append(".pyweb/cache/")
        gitignore.write_text("\n".join(lines) + "\n")
        click.echo("Added .pyweb/cache/ to .gitignore")


@cli.command()
@click.argument("file")
@click.argument("name")
@click.argument("start_line", type=int)
@click.argument("end_line", type=int)
@click.option("--parent", default=None, help="Parent fragment ID.")
@click.option("--prose", default=None, help="Prose/explanation for this fragment.")
@click.pass_context
def add(ctx: click.Context, file: str, name: str, start_line: int, end_line: int,
        parent: str | None, prose: str | None) -> None:
    """Define a new fragment over a line range."""
    store = _get_store(ctx)
    _require_init(store)
    try:
        frag = store.create_fragment(
            file, name, Range(start_line, 0, end_line, 0),
            parent_id=parent, prose=prose,
        )
        click.echo(f"Created fragment '{frag.name}' ({frag.id}) [{start_line}:{0} - {end_line}:{0}]")
    except ValidationError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("add-inline")
@click.argument("file")
@click.argument("name")
@click.argument("line", type=int)
@click.argument("start_col", type=int)
@click.argument("end_col", type=int)
@click.option("--parent", default=None, help="Parent fragment ID.")
@click.pass_context
def add_inline(ctx: click.Context, file: str, name: str, line: int,
               start_col: int, end_col: int, parent: str | None) -> None:
    """Define an inline fragment over a column range within a single line."""
    store = _get_store(ctx)
    _require_init(store)
    try:
        frag = store.create_fragment(
            file, name, Range(line, start_col, line, end_col),
            parent_id=parent,
        )
        click.echo(f"Created inline fragment '{frag.name}' ({frag.id}) [{line}:{start_col} - {line}:{end_col}]")
    except ValidationError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("file")
@click.argument("fragment_id")
@click.pass_context
def rm(ctx: click.Context, file: str, fragment_id: str) -> None:
    """Remove a fragment (code stays in source, only metadata removed)."""
    store = _get_store(ctx)
    _require_init(store)
    try:
        store.delete_fragment(file, fragment_id)
        click.echo(f"Removed fragment {fragment_id}")
    except ValidationError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("file")
@click.argument("fragment_id")
@click.argument("new_name")
@click.pass_context
def rename(ctx: click.Context, file: str, fragment_id: str, new_name: str) -> None:
    """Rename a fragment."""
    store = _get_store(ctx)
    _require_init(store)
    try:
        store.rename_fragment(file, fragment_id, new_name)
        click.echo(f"Renamed fragment {fragment_id} → '{new_name}'")
    except ValidationError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("file")
@click.pass_context
def ls(ctx: click.Context, file: str) -> None:
    """List fragments as an indented tree."""
    store = _get_store(ctx)
    _require_init(store)

    ff = store.load_file(file)
    if ff is None:
        click.echo("No fragments defined for this file.")
        return

    by_id = {f.id: f for f in ff.fragments}

    def print_tree(fragment_id: str, depth: int) -> None:
        f = by_id[fragment_id]
        r = f.range
        indent = "  " * depth
        status = " [orphaned]" if r.is_orphaned() else ""
        click.echo(f"{indent}{f.name} ({f.id}) [{r.start_line}:{r.start_col} - {r.end_line}:{r.end_col}]{status}")
        for cid in f.children:
            if cid in by_id:
                print_tree(cid, depth + 1)

    # Find roots
    child_ids: set[str] = set()
    for f in ff.fragments:
        child_ids.update(f.children)
    roots = [f for f in ff.fragments if f.id not in child_ids]

    # Sort roots by start position
    roots.sort(key=lambda f: (f.range.start_line, f.range.start_col))
    for root in roots:
        print_tree(root.id, 0)


@cli.command()
@click.argument("file")
@click.pass_context
def check(ctx: click.Context, file: str) -> None:
    """Validate fragment integrity."""
    store = _get_store(ctx)
    _require_init(store)

    errors = store.validate(file) + store.validate_bounds(file)
    if errors:
        for e in errors:
            click.echo(f"  ERROR: {e}", err=True)
        sys.exit(1)
    else:
        click.echo("OK — no validation errors.")


@cli.command()
@click.argument("file")
@click.pass_context
def expand(ctx: click.Context, file: str) -> None:
    """Print the source file (expanded view)."""
    store = _get_store(ctx)
    source_path = store.project_root / file
    if not source_path.exists():
        click.echo(f"Error: file '{file}' not found.", err=True)
        sys.exit(1)
    click.echo(source_path.read_text(), nl=False)


@cli.command()
@click.argument("file")
@click.option("--fragment", "-f", default=None, help="Show only this fragment subtree (ID or name).")
@click.pass_context
def view(ctx: click.Context, file: str, fragment: str | None) -> None:
    """Print hierarchical view to stdout."""
    store = _get_store(ctx)
    _require_init(store)

    engine = SyncEngine(store, store.project_root)

    # Resolve name to ID if needed
    frag_id = fragment
    if fragment is not None:
        f = store.get_fragment_by_name(file, fragment)
        if f is not None:
            frag_id = f.id

    text = engine.render_hierarchical_text(file, fragment_id=frag_id)
    if text:
        click.echo(text, nl=False)
    else:
        click.echo("No fragments defined for this file.")


@cli.command()
@click.argument("file")
@click.option("--all", "anchor_all", is_flag=True, default=False, help="Re-anchor all tracked files.")
@click.pass_context
def anchor(ctx: click.Context, file: str, anchor_all: bool) -> None:
    """Re-anchor fragments to current file content."""
    store = _get_store(ctx)
    _require_init(store)

    files_to_anchor = [file]
    if anchor_all:
        import json
        config = json.loads((store.pyweb_dir / "config.json").read_text())
        files_to_anchor = config.get("tracked_files", [])

    for fp in files_to_anchor:
        ff = store.load_file(fp)
        if ff is None:
            click.echo(f"No fragments for {fp}, skipping.")
            continue

        source_path = store.project_root / fp
        if not source_path.exists():
            click.echo(f"Warning: source file '{fp}' not found.", err=True)
            continue

        new_content = source_path.read_text()
        new_hash = store.content_hash(new_content)

        if new_hash == ff.content_hash:
            click.echo(f"{fp}: already up to date.")
            continue

        # Get old content from cache
        old_content = store.load_cache(fp)
        if old_content is None:
            click.echo(f"{fp}: no cached content, re-caching without anchoring.")
            store.save_cache(fp, new_content)
            ff.content_hash = new_hash
            store.save_file(ff)
            continue

        edits = DiffAnchorer.compute_line_edits(old_content, new_content)
        updated_frags = DiffAnchorer.apply_edits(ff.fragments, edits)

        shifted = sum(1 for old, new in zip(ff.fragments, updated_frags) if old.range != new.range)
        orphaned = sum(1 for f in updated_frags if f.range.is_orphaned())

        ff.fragments = updated_frags
        ff.content_hash = new_hash
        store.save_file(ff)
        store.save_cache(fp, new_content)

        click.echo(f"{fp}: shifted {shifted} fragments, {orphaned} orphaned.")


@cli.command("import")
@click.argument("pwb_file")
@click.argument("output_file")
@click.option("--top-level", "-f", default="*", help="Top-level fragment name to expand.")
@click.pass_context
def import_cmd(ctx: click.Context, pwb_file: str, output_file: str, top_level: str) -> None:
    """Import a .pwb file: tangle it and create sidecar fragments."""
    store = _get_store(ctx)
    if not store.is_initialized():
        store.init()

    from pyweb.core.importer import import_pwb

    pwb_path = Path(pwb_file).resolve()
    output_path = (store.project_root / output_file).resolve()

    if not pwb_path.exists():
        click.echo(f"Error: file '{pwb_file}' not found.", err=True)
        sys.exit(1)

    import_pwb(pwb_path, output_path, store.project_root, top_level)

    rel = str(output_path.relative_to(store.project_root))
    ff = store.load_file(rel)
    n = len(ff.fragments) if ff else 0
    click.echo(f"Imported {pwb_file} → {output_file} ({n} fragments created)")

@cli.command()
@click.argument("file")
@click.argument("fragment_id")
@click.argument("start_line", type=int)
@click.argument("end_line", type=int)
@click.pass_context
def resize(ctx: click.Context, file: str, fragment_id: str, start_line: int, end_line: int) -> None:
    """Resize a fragment to a new line range."""
    store = _get_store(ctx)
    _require_init(store)
    try:
        store.resize_fragment(file, fragment_id, Range(start_line, 0, end_line, 0))
        click.echo(f"Resized fragment {fragment_id} → [{start_line}:0 - {end_line}:0]")
    except ValidationError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def some_dummy_ass_fun():
    print()
    print()
    print()
    print()

    for i in range(10):
        # inner stuffs??
        a = 1+2
        b = 'ab' + 'dc'
        print()

    # nice
    d = {i:i*i for i in range(20)}