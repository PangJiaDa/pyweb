# pyweb v2 — Specification

## 1. What This Is

A tool that lets you define a tree of named code regions (fragments) over any source file, then view and edit the code as either (a) normal expanded source or (b) a hierarchical fragment view. Edits in either view propagate to the other. The source files are never modified by the tool's metadata — it lives in a sidecar.

## 2. Concepts

### Fragment
A named region of a source file. Defined by:
- `id`: unique identifier (UUID)
- `name`: human-readable label (e.g. "error handling", "main loop")
- `file`: path to the source file (relative to project root)
- `range`: start line/col to end line/col (0-indexed, end-exclusive)
- `children`: ordered list of child fragment IDs (nesting)
- `prose`: optional markdown string attached to this fragment

Fragments form a **forest** (multiple roots). A fragment's range must fully contain all its children's ranges. Children must not overlap. Lines/columns not claimed by any fragment are "unowned" — visible in expanded view, invisible in hierarchical view unless they fall between sibling fragments (then shown as context).

### Inline Fragment
A fragment whose range is a substring within a single line (start_line == end_line, start_col != 0 or end_col != line length). Same data structure, just narrower range. No special handling — the system is range-based, not line-based.

### Sidecar Store
All fragment metadata lives in `.pyweb/` at the project root. Structure:

```
.pyweb/
  config.json          # project-level settings
  fragments/
    <source_file_path>.json   # fragments for that file
```

Example `.pyweb/fragments/src/main.py.json`:
```json
{
  "file": "src/main.py",
  "content_hash": "sha256:abc123...",
  "fragments": [
    {
      "id": "f1a2b3",
      "name": "initialization",
      "range": { "start_line": 0, "start_col": 0, "end_line": 24, "end_col": 0 },
      "children": ["f4d5e6", "f7g8h9"],
      "prose": "Sets up logging and config before anything else runs."
    },
    {
      "id": "f4d5e6",
      "name": "logging setup",
      "range": { "start_line": 2, "start_col": 0, "end_line": 10, "end_col": 0 },
      "children": [],
      "prose": null
    }
  ]
}
```

`content_hash` is the sha256 of the source file at the time fragments were last anchored. Used to detect when re-anchoring is needed.

### Source Map
A derived, in-memory structure (not persisted) built from the fragment store. Maps every line/col range in the source file to its owning fragment (if any). Used for:
- Looking up which fragment a source edit belongs to
- Rendering the hierarchical view
- Navigating between views (cursor position preservation)

Built by walking the fragment tree depth-first. Rebuilt on any fragment or source change.

### Anchoring
When the source file changes externally (git pull, coworker edit, rebase), fragment ranges drift. Anchoring = updating those ranges to match the new file.

**Algorithm:**
1. On load or file change, compare `content_hash` in sidecar to actual file hash.
2. If they differ, compute a line-level diff between the cached content and the current content.
3. For each diff hunk (insert N lines at line L, delete N lines at line L):
   - Shift all fragment ranges accordingly: ranges after the hunk shift by +N or -N lines.
   - Ranges that overlap a deletion: shrink. If fully deleted: mark fragment as `orphaned` (keep in store, warn user).
4. For inline fragments affected by within-line changes: compute character-level diff for those specific lines, shift column offsets.
5. Update `content_hash`. Persist.

**Content caching for diffing without git:**
The sidecar stores a copy of each tracked file's content at last-known-good state in `.pyweb/cache/<file_path>`. This is what we diff against. Updated after each successful anchor. This makes the tool VCS-agnostic.

**With git (optimization):**
If the project is a git repo, use `git diff` output directly instead of diffing cached content. Faster for large files, and handles renames via `git diff --follow`.

## 3. Core Library API

Python package: `pyweb.core`

### Data Types

```python
@dataclass
class Range:
    start_line: int    # 0-indexed
    start_col: int     # 0-indexed
    end_line: int       # 0-indexed, exclusive
    end_col: int        # 0-indexed, exclusive

@dataclass
class Fragment:
    id: str
    name: str
    file: str           # relative path
    range: Range
    children: list[str] # ordered child IDs
    prose: str | None

@dataclass
class FileFragments:
    file: str
    content_hash: str
    fragments: list[Fragment]
```

### FragmentStore

Reads/writes `.pyweb/fragments/*.json`.

```python
class FragmentStore:
    def __init__(self, project_root: Path) -> None: ...

    # CRUD
    def load_file(self, file_path: str) -> FileFragments | None: ...
    def save_file(self, file_frags: FileFragments) -> None: ...
    def get_fragment(self, file_path: str, fragment_id: str) -> Fragment | None: ...

    # Fragment operations
    def create_fragment(self, file_path: str, name: str, range: Range,
                        parent_id: str | None = None, prose: str | None = None) -> Fragment: ...
    def delete_fragment(self, file_path: str, fragment_id: str) -> None: ...
    def rename_fragment(self, file_path: str, fragment_id: str, new_name: str) -> None: ...
    def move_fragment(self, file_path: str, fragment_id: str, new_parent_id: str | None) -> None: ...
    def set_prose(self, file_path: str, fragment_id: str, prose: str | None) -> None: ...

    # Queries
    def get_roots(self, file_path: str) -> list[Fragment]: ...
    def get_children(self, file_path: str, fragment_id: str) -> list[Fragment]: ...
    def fragment_at(self, file_path: str, line: int, col: int) -> Fragment | None: ...
```

### SourceMap

Built from FragmentStore. Not persisted.

```python
class SourceMap:
    def __init__(self, file_frags: FileFragments) -> None: ...

    def fragment_at(self, line: int, col: int) -> Fragment | None: ...
    def range_of(self, fragment_id: str) -> Range | None: ...
    def depth_first_walk(self) -> Iterator[tuple[Fragment, int]]: ...  # (fragment, depth)
```

### DiffAnchorer

Adjusts fragment ranges when source changes.

```python
@dataclass
class LineEdit:
    """A contiguous edit: delete `old_count` lines at `line`, insert `new_count` lines."""
    line: int
    old_count: int
    new_count: int

class DiffAnchorer:
    @staticmethod
    def compute_line_edits(old_content: str, new_content: str) -> list[LineEdit]: ...

    @staticmethod
    def apply_edits(fragments: list[Fragment], edits: list[LineEdit]) -> list[Fragment]:
        """Returns updated fragments. Fragments fully deleted are marked with range (-1,-1,-1,-1)."""
        ...
```

### SyncEngine

Propagates edits between views.

```python
class SyncEngine:
    def __init__(self, store: FragmentStore, project_root: Path) -> None: ...

    def on_source_changed(self, file_path: str, old_content: str, new_content: str) -> None:
        """Source file was edited. Re-anchor fragments."""
        ...

    def on_fragment_content_changed(self, file_path: str, fragment_id: str, new_code: str) -> str:
        """User edited code in hierarchical view. Returns the full updated source file content.
        Replaces the fragment's range in the source file with new_code.
        Re-anchors all sibling/child fragments affected by the size change."""
        ...

    def expanded_view(self, file_path: str) -> str:
        """Returns the source file content (just reads the file — this IS the expanded view)."""
        ...

    def hierarchical_view(self, file_path: str) -> list[HierarchicalNode]:
        """Returns the fragment tree with code and prose for rendering."""
        ...

@dataclass
class HierarchicalNode:
    fragment: Fragment
    code: str           # the source code owned by this fragment (excluding children's code)
    children: list[HierarchicalNode]
```

## 4. CLI Interface

Single entry point: `pyweb`

```
pyweb init
    Initialize .pyweb/ in current directory. Add .pyweb/cache/ to .gitignore.

pyweb add <file> <name> <start_line> <end_line> [--parent <fragment_id>] [--prose <text>]
    Define a new fragment over a line range.

pyweb add-inline <file> <name> <line> <start_col> <end_col> [--parent <fragment_id>]
    Define an inline fragment over a column range within a single line.

pyweb rm <file> <fragment_id>
    Remove a fragment (code stays in source, only metadata removed).

pyweb rename <file> <fragment_id> <new_name>
    Rename a fragment.

pyweb ls <file>
    List fragments as an indented tree.
    Output format:
      initialization (f1a2b3) [0:0 - 24:0]
        logging setup (f4d5e6) [2:0 - 10:0]
        config loading (f7g8h9) [12:0 - 24:0]

pyweb view <file> [--fragment <id_or_name>]
    Print hierarchical view to stdout. Shows fragment names, prose, and code.
    If --fragment given, show only that subtree.

pyweb expand <file>
    Print the source file (trivial — cat the file). Exists for symmetry.

pyweb anchor <file>
    Re-anchor fragments to current file content. Run after external changes.
    Reports: shifted N fragments, M orphaned.

pyweb anchor --all
    Re-anchor all tracked files.

pyweb check <file>
    Validate fragment integrity: no overlaps, children within parents, ranges within file bounds.

pyweb import <pwb_file> <output_source_file>
    Import a .pwb file: tangle it to produce the source file, then create fragment
    definitions in the sidecar matching the original chunk structure.
    Bridge from pyweb v1 to v2.
```

All commands output to stdout, errors to stderr. Exit code 0 on success, 1 on error.

## 5. Sidecar File Format

### `.pyweb/config.json`
```json
{
  "version": 1,
  "tracked_files": ["src/main.py", "src/utils.py"]
}
```

### `.pyweb/fragments/<file_path>.json`
As shown in section 2. One file per tracked source file. Path mirrors source path with `.json` suffix.

### `.pyweb/cache/<file_path>`
Verbatim copy of the source file at last successful anchor. Used for diffing without git.

## 6. Hierarchical View Output Format

For `pyweb view`, output is a readable text format:

```
=== initialization ===
Sets up logging and config before anything else runs.

  import logging
  import json

  --- logging setup ---
  logger = logging.getLogger(__name__)
  handler = logging.StreamHandler()
  logger.addHandler(handler)

  --- config loading ---
  with open('config.json') as f:
      config = json.load(f)
```

Rules:
- `=== name ===` for root fragments
- `--- name ---` for nested fragments
- Prose (if any) printed in italics/indented below the header
- Code printed verbatim
- Children rendered inline at their position within the parent's code
- Unowned lines between siblings shown as-is

## 7. Validation Rules

Enforced on every mutation (create, move, edit):

1. **No overlap.** Sibling fragments must not have overlapping ranges.
2. **Parent contains children.** Every child's range must be fully within its parent's range.
3. **Ranges within file bounds.** No range extends past EOF.
4. **Unique names per file.** Fragment names must be unique within a file (IDs are always unique).
5. **No cycles.** The parent-child graph is a forest.

Violations are errors, not warnings. The operation is rejected.

## 8. Implementation Plan

### Phase 1: Core data model + store
- `Range`, `Fragment`, `FileFragments` dataclasses
- `FragmentStore`: read/write JSON sidecar files
- Validation logic (rules from section 7)
- Tests: round-trip serialization, validation rejects bad input

### Phase 2: Anchoring
- `DiffAnchorer`: compute line edits from old/new content, apply to fragment ranges
- Content cache in `.pyweb/cache/`
- Tests: insert lines, delete lines, mixed edits, fragment shrinking, orphan detection

### Phase 3: CLI — structure commands
- `pyweb init`, `add`, `rm`, `rename`, `ls`, `check`
- Uses FragmentStore and DiffAnchorer

### Phase 4: Views
- `SourceMap`: build from fragment tree, lookup by position
- `SyncEngine.hierarchical_view()`: walk tree, extract code slices, render
- `pyweb view`, `pyweb expand`
- Tests: view output matches expected format

### Phase 5: Bidirectional sync
- `SyncEngine.on_source_changed()`: detect file changes, re-anchor
- `SyncEngine.on_fragment_content_changed()`: splice edited code back into source, re-anchor siblings
- Tests: edit in source → fragments update. Edit fragment → source updates. Round-trip stability.

### Phase 6: Import bridge
- `pyweb import`: tangle a .pwb file, create sidecar fragments matching the original chunk structure
- Reuses existing `main.py` tangle logic + source map from expansion

### Phase 7: Editor integration (future)
- VS Code extension: thin adapter calling `pyweb` CLI or linking core library
- LSP server mode: `pyweb lsp` (persistent process, JSON-RPC over stdin/stdout)
- Not in scope for initial Python implementation

## 9. Dependencies

- Python >= 3.11
- `click` (CLI framework, already in use)
- `difflib` (stdlib, for computing diffs)
- No other external dependencies for core

## 10. What This Spec Does NOT Cover

- Editor/IDE integration details (VS Code extension, LSP protocol messages)
- Multi-file fragments (a fragment spanning multiple source files)
- Collaborative editing (multiple users editing fragments simultaneously)
- Fragment versioning / undo history (rely on git for this)
- Prose rendering beyond plain text (markdown rendering is the editor's job)
