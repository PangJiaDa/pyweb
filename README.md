# PyWeb

Define named, hierarchical code regions over any source file using comment markers. Works with any language, any editor, any tool.

## How It Works

You annotate your source code with markers inside comments:

```python
# @pyweb:start id="f1" name="persistence"
class Todo:
    id: int
    title: str
    done: bool = False

class TodoStore:
    def __init__(self):
        self._todos = {}
    # @pyweb:start id="f2" name="CRUD operations"
    def add(self, title): ...
    def get(self, todo_id): ...
    def delete(self, todo_id): ...
    # @pyweb:end id="f2"
# @pyweb:end id="f1"

# @pyweb:start id="f3" name="HTTP handler"
class RequestHandler:
    ...
# @pyweb:end id="f3"
```

The markers define a tree of named fragments. Nesting is inferred from marker order (stack-based, like HTML). The code between markers is completely normal — all existing tools (LSPs, git, debuggers, linters) work as before.

The [VS Code extension](https://github.com/PangJiaDa/pyweb-vscode) gives you a sidebar tree view, folding, navigation, and commands to create/rename/remove fragments without typing markers by hand.

## Install

```bash
pip install git+https://github.com/PangJiaDa/pyweb.git
```

Requires Python 3.11+.

## CLI Usage

```bash
pyweb parse main.py              # output fragment tree as JSON
pyweb ls main.py                 # print fragment tree as indented text
pyweb add main.py "setup" 10 25  # insert markers around lines 10-25
pyweb rm main.py <fragment_id>   # remove markers (keeps code)
pyweb rename main.py <id> "new"  # rename a fragment
pyweb resize main.py <id> 8 30   # move markers to new line range
pyweb prose main.py <id> "text"  # set prose on a fragment
pyweb check main.py              # validate marker integrity
pyweb view main.py               # print hierarchical view
pyweb expand main.py             # print raw source file
```

All commands take `-p <project_root>` to specify the working directory.

## Marker Format

Works with any language — the parser looks for `@pyweb:start`, `@pyweb:end`, and `@pyweb:prose` inside any comment style:

| Language | Marker example |
|----------|---------------|
| Python, Ruby, Shell | `# @pyweb:start id="f1" name="init"` |
| JS, TS, Java, Go, Rust | `// @pyweb:start id="f1" name="init"` |
| HTML, XML | `<!-- @pyweb:start id="f1" name="init" -->` |
| CSS | `/* @pyweb:start id="f1" name="init" */` |
| Lua, SQL, Haskell | `-- @pyweb:start id="f1" name="init"` |

60+ file extensions supported out of the box. The comment style is only needed when the CLI inserts markers — the parser recognizes markers regardless of comment syntax.

## Partial Parse / Error Recovery

Markers can be corrupted (someone deletes one by accident) and the parser handles it gracefully:

- **Missing end marker** — fragment extends to its parent's end, or EOF. Warning emitted.
- **Orphaned end marker** — ignored. Warning emitted.
- **Missing inner end** — auto-closed when parent closes. Warning emitted.
- **Duplicate IDs** — second one skipped. Warning emitted.

Run `pyweb check <file>` to see all warnings.

## Architecture

```
pyweb/core/
  parser.py     — stack-based marker parser, builds fragment tree
  writer.py     — insert/remove/modify markers in source files
  comments.py   — language → comment syntax mapping
  models.py     — Range, Fragment data structures
```

The CLI (`pyweb/cli.py`) wraps the core library. Editor extensions call the CLI and consume its JSON output. See [INTEGRATION.md](INTEGRATION.md) for details on building editor integrations.

## Background

This project started as a [noweb](https://www.cs.tufts.edu/~nr/noweb/)-style macro expander for literate programming (the `main.py` and `.pwb` files in this repo). It evolved into a general-purpose tool for defining hierarchical code regions over any source file, after realizing that the valuable part wasn't the macro expansion — it was the ability to name and navigate code at a level of abstraction above functions and files.

The original literate programming tools (`.pwb` → tangled source) are still in the repo and still work, but the marker-based approach is the primary direction going forward.

## Related

- [pyweb-vscode](https://github.com/PangJiaDa/pyweb-vscode) — VS Code extension
- [INTEGRATION.md](INTEGRATION.md) — guide for building integrations with other editors
- [SPEC.md](SPEC.md) — original v2 spec (sidecar-based, now superseded by markers)
