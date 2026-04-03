# What is PYWEB?
PYWEB is a macro expansion system. 
If you want to create a piece of text (a source code file, for example), and would want to specify it as chunks of text that can further expand to other chunks of text, this might be able to do that.

# Motivations
I wanted to try some ideas from Knuth's Literate Programming, but most literate programming tools I could find (WEB / CWEB / nuweb) were too complicated for me to set up.
The simplest one I could find, [noweb](https://www.cs.tufts.edu/~nr/noweb/), didn't have well supported installation for Windows (which I use). 

So this project is mostly just copying (an extremely barebones subset of) the "tangle" functionality of noweb (the other being "weave"), with a few tweaks.
Should work on any programming languages because whitespace indentation is respected.

# Should you use this tool?
- Pros: 
  - It's nice when the structure of the problem at hand matches this kind of "top-down" recursive substitution of code fragments.
  - Can intersperse documentation and comments among code more flexibly than with traditional comments.
- Cons: 
  - You lose all intelli-sense abilities (code completion, syntax highlighting, LSP type checking, refactoring tools). It's just plain text.
  - Development flow now has 1 more stage. Web file has to be tangled, before the output file (which is traditionally the source code file that you write out directly) is then ran through all the normal checks (syntax checkers / type checkers / further compilation with other source code files, etc)
  - Collaboration using line-based version control systems might detect more conflicts.
- Neutral:
  - Traditional programming has the code well-structured, but the explanation of the code fragmented. This makes working with the code easy, but understanding it hard.
  - Literate programming has the explanation of the code well-structured, but the code fragmented. This makes understanding the code easy, but refactoring it hard.


# Usage:
```
python main.py --src_path PWB_SOURCE_FILE [--top_lvl_fragment FRAGMENT_NAME] [--include_src_lineno]
```

# Credits
The idea for which features to implement, and the main explanation of each of the features, is largely copied from the [noweb man pages](https://man.cx/noweb(1)), with some edits where this implementation has different functionality. The syntax has been altered with inspiration from [CWEB](https://www-cs-faculty.stanford.edu/~knuth/cweb.html) to allow inline macro expansion.

# Description of Features
- A noweb file is a sequence of chunks, which may appear in any order. A chunk may contain code or documentation. 
- Documentation chunks begin with a line that starts with an `@` sign followed by a space or newline. They have no names.
- Code chunks begin with `@<chunk name@>=` at the start of a line. 
  - If a code chunk is meant to be inline expanded, it should only be 1 line long. This line of code can start on the same line as the chunk definition, or on its own line below. See examples below.
  - If a code chunk is meant to be a multiline code chunk, it is recommended to start the code text only on a newline to make the resulting whitespace after substitution predictable.
- The code chunk definition opening tag `@<` must be in the first column of a line.
- Chunks are terminated by the beginning of another chunk, or by end of file.
- [To be implemented] If the first line in the file does not mark the beginning of a chunk, it is assumed to be the first line of a documentation chunk.
- Documentation chunks are completely ignored when tangling the output.
- Code chunks contain program source code and references to other code chunks.
- Several code chunks may have the same name; pyweb concatenates their definitions to produce a single chunk, just as noweb, which this is copied from, does.
- A code-chunk definition is like a macro definition; it contains references to other chunks, which are themselves expanded, and so on. 
- pyweb’s output is readable; it preserves the indentation of expanded chunks with respect to the chunks in which they appear. This is essential when using it for whitespace-significant programming languages (like Python).
  - Inline references, however, are expanded without any leading or trailing whitespace. It is important that inline chunks don't contain newlines characters, or the resulting inline expanded text could be syntactically incorrect.
- if the `--include_src_lineno` flag is set, pyweb includes a comment in the tangled output, above a code fragment that has been expanded, showing the line number in the pyweb source code where that fragment was defined, or concatenated to an existing fragment.

# Vision
One source of truth, N views into it, edit at any level. Flick between whichever representation is most useful right now — fully expanded source code, hierarchical fragments, prose-annotated outline — and edits in any view propagate to all others. Each view can be fed into tools that work best with that representation: the expanded source into LSPs, git, and debuggers; the hierarchical view into documentation generators or structural editors. Changes made by any tool in any view propagate back to the source of truth, and therefore to every other view. The current tool is a starting point: a one-way expander (`.pwb` → source). The goal is to close the loop.

# Practical Consideration: Zero-Buy-In Overlay

This tool should work on any existing, unannotated codebase without requiring team adoption or polluting source files.

- **Sidecar metadata, not source annotations.** Fragment definitions (named regions, hierarchy, prose) live in a `.pyweb/` directory, gitignored. The source files are never modified by the tool. Coworkers see clean, normal code.
- **Anchoring via git diffs.** When the source changes (coworker commits, rebases, etc.), the sidecar's line ranges are updated by applying the same line insertions/deletions reported by `git diff`. This is deterministic — no fuzzy content matching needed. For real-time edits before commit, the extension computes its own diffs on file save.
- **No tool exists that does this.** The closest precedents are [Leo's @clean](https://leo-editor.github.io/leo-editor/) (bidirectional outline-to-source sync via the Mulder/Ream algorithm, but requires authoring in Leo) and [VS Code CodeTour](https://github.com/microsoft/codetour) (sidecar JSON on unmodified files, but read-only). Nothing combines sidecar-only fragment definitions, bidirectional editing, and zero team buy-in on existing codebases.

# Known Limitations & Future Directions

1. **No IDE support for `.pwb` files.** No jump-to-definition for fragment references, no rename-fragment, no autocomplete for fragment names. You're working with plain text.

2. **No IDE support for the target language within fragments.** Code inside `.pwb` chunks has no syntax highlighting, type checking, or language-aware refactoring. Renaming a variable that spans multiple fragments is entirely manual.

3. **Cannot switch between expanded and unexpanded views.** Sometimes you want to see the hierarchical structure; sometimes you want to see the fully expanded output. There's no way to flick between these two representations of the same code, or to edit in the expanded view and have changes propagate back to the right fragment.

4. **One-way compilation with no round-tripping.** The `.pwb` → tangled source flow is one-directional. The tangled output integrates fine with git, LSPs, and other tools, but edits to the output can't flow back to the `.pwb` source. There's no source map or bidirectional sync.

5. **Can't be used on existing codebases.** You can't take an existing source file, define arbitrary named regions within it, and get the hierarchical view — you'd have to rewrite it as a `.pwb` file. Ideally, the hierarchy metadata (named folding regions) could live as annotations in normal source files, so the source file remains the primary artifact and all existing tools continue to work.

These limitations point toward a more general tool: one that maintains a **tree of named code regions** as the underlying model, with the `.pwb` format and annotated source files as two interchangeable views of that same tree — editable from either side, with full IDE support because the source file is always valid target-language code.

# Examples
## Documentation chunk starts: inline / newline start + single line / multiline chunks

`source.pwb`
```
@ This is the start of a doc chunk. Starting to type comments can be on the same line as the `@` symbol.

@
This is also another doc chunk. The text can start on the next line too.

@


This is yet another doc chunk. But they're treated all the same when tangling: they are ignored.
```
## Multiline code fragment expansion example (with and without indentation, concatenation to existing fragments, source lineno info)

`source.pwb`
```
@ At the top level block of `Indentation demonstration`, the 2 code fragments under it are not indented relatative to the top level code block.

@<Indentation demonstration@>=
@<Variable declarations@>
@<Print stuff@>

@<Variable declarations@>=
i = 0
j = 0

@ Notice that the code fragments inside the while loop are indented.
Every line in the expansion of those fragments will be indented by that amount.

@<Print stuff@>=
while i <= 10 and j <= 10:
    @<Print i and j@>
    @<Increment i and j@>
  
@<Print i and j@>=
print(i, j)

@<Increment i and j@>=
i += 1
j += 1
```

`output.py`, if `--include_src_lineno` is enabled.
```python
# <<*>>, line 3
# <<Variable declarations>>, line 7
i = 0
j = 0
# <<Print stuff>>, line 14
while i <= 10 and j <= 10:
    # <<Print i and j>>, line 20
    print(i, j)
    # <<Increment i and j>>, line 23
    i += 1
    j += 1
# line 30
x = y = z = 123
```

`output.py`, if `--include_src_lineno` is disabled.
```python
i = 0
j = 0
while i <= 10 and j <= 10:
    print(i, j)
    i += 1
    j += 1
x = y = z = 123
```

## Inline code fragments
`source.pwb`
```
@ The inline expressions can be defined on the same line without space after the closing tag, with arbitrary amount of whitespace,
or on a newline entirely. They just must be a single line in total.

@<*@>=
print(@<inline expr 1@>, @<inline expr 2@>, @<inline expr 3@>)

@<inline expr 1@>="A"
@<inline expr 2@>=          3+4*5-6
@<inline expr 3@>=

            {i: i*i for i in range(20)}
```

`output.py`
```python
print("A", 3+4*5-6, {i: i*i for i in range(20)})
```