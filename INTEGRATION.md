# Integrating PyWeb with Other Editors

PyWeb's core is a Python CLI. Any editor can integrate with it by shelling out to the CLI and reading the sidecar JSON files directly. This document describes the interface.

## Prerequisites

- Python 3.11+
- The `pyweb` package available (clone the repo, run from the directory)
- A project initialized with `python3 -m pyweb.cli init`

## CLI Interface

All commands use this pattern:

```bash
python3 -m pyweb.cli -p <project_root> <command> [args...]
```

`-p` sets the project root (where `.pyweb/` lives). Defaults to `.`.

### Commands

| Command | Description | Output |
|---------|-------------|--------|
| `init` | Initialize `.pyweb/` in project root | Status message |
| `add <file> <name> <start_line> <end_line> [--parent <id>] [--prose <text>]` | Create a fragment over a line range | Fragment ID in output |
| `add-inline <file> <name> <line> <start_col> <end_col> [--parent <id>]` | Create an inline (column-range) fragment | Fragment ID in output |
| `rm <file> <fragment_id>` | Remove a fragment (keeps source code) | Status message |
| `rename <file> <fragment_id> <new_name>` | Rename a fragment | Status message |
| `ls <file>` | Print fragment tree (indented text) | Indented tree |
| `check <file>` | Validate fragment integrity | "OK" or error list |
| `expand <file>` | Print the source file content | Source code |
| `view <file> [--fragment <id_or_name>]` | Print hierarchical view | Formatted text |
| `anchor <file>` | Re-anchor fragments after source changed | Shift/orphan counts |

All commands exit 0 on success, 1 on error. Errors go to stderr.

### Parsing output

The `add` command outputs:
```
Created fragment 'name' (abc12345) [0:0 - 10:0]
```
Extract the ID from between parentheses.

The `ls` command outputs:
```
root_name (id) [start_line:start_col - end_line:end_col]
  child_name (id) [start_line:start_col - end_line:end_col]
```
Two-space indentation per nesting level.

## Sidecar JSON Format (Direct File Access)

For richer data, read the JSON files directly instead of parsing CLI output.

### `.pyweb/config.json`
```json
{
  "version": 1,
  "tracked_files": ["src/main.py"]
}
```

### `.pyweb/fragments/<file_path>.json`

One file per tracked source file. Path mirrors the source path with `.json` appended.

```json
{
  "file": "src/main.py",
  "content_hash": "sha256:abc123...",
  "fragments": [
    {
      "id": "f1a2b3c4",
      "name": "initialization",
      "file": "src/main.py",
      "range": {
        "start_line": 0,
        "start_col": 0,
        "end_line": 24,
        "end_col": 0
      },
      "children": ["d5e6f7g8"],
      "prose": "Sets up logging and config."
    }
  ]
}
```

**Range semantics:**
- 0-indexed lines and columns
- `end_line` and `end_col` are exclusive (like Python slicing)
- Orphaned fragments have range `{-1, -1, -1, -1}`

**Fragment tree structure:**
- `children` is an ordered list of child fragment IDs
- Root fragments are those whose ID does not appear in any other fragment's `children` list
- Fragments form a forest (multiple roots allowed)

### `.pyweb/cache/<file_path>`

Verbatim copy of the source file at last successful anchor. Used for diffing.

## Editor Integration Patterns

### 1. Fragment Tree View
Read `.pyweb/fragments/<file>.json`, compute roots (IDs not in any `children` list), render as a tree. Click → navigate to `range.start_line`.

### 2. Decorations / Gutter Marks
For each fragment, highlight lines `start_line` to `end_line - 1`. Show fragment name as an inline hint on the first line.

### 3. Create Fragment from Selection
When user selects code and triggers "create fragment":
1. Get selection start/end lines
2. Prompt for name
3. Run `pyweb add <file> <name> <start_line> <end_line>`
4. Refresh tree + decorations

### 4. Auto-Anchor on Save
On file save:
1. Run `pyweb anchor <file>`
2. Refresh tree + decorations
This keeps fragment ranges in sync with edits.

### 5. Hierarchical View
Run `pyweb view <file>` and display the output in a side panel. The output format uses `=== name ===` for root fragments and `--- name ---` for nested ones.

### 6. Bidirectional Sync (Advanced)
For editing in the hierarchical view and propagating back to source, use the Python API directly:

```python
from pyweb.core.store import FragmentStore
from pyweb.core.sync import SyncEngine

store = FragmentStore(project_root)
engine = SyncEngine(store, project_root)

# Edit a fragment's code → source file updates
engine.on_fragment_content_changed("src/main.py", fragment_id, new_code)

# Source file changed externally → fragments re-anchor
engine.on_source_changed("src/main.py", old_content, new_content)
```

## Validation Rules

These are enforced by the CLI/core and useful to know for UI feedback:

1. Fragment names must be unique within a file
2. Sibling fragments must not overlap
3. Children must be fully contained within their parent's range
4. Fragment ranges must be within file bounds
5. The parent-child graph must be acyclic (a forest)
