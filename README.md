# What is PYWEB?
PYWEB is a macro expansion system. If you want to create a piece of text (a source code file, for example), and would want to specify it as chunks of text that can further expand to other chunks of text. This might be able to do that.

# Motivations
I wanted to try some ideas from Knuth's Literate Programming, but most literate programming tools I could find (WEB / CWEB / nuweb) were too complicated for me to set up. The simplest one I could find, noweb, didn't have well supported installation for Windows (which I use). 

So this project is mostly just copying the "tangle" functionality of [noweb](https://www.cs.tufts.edu/~nr/noweb/) (the other being "weave"), with a few tweaks.
Should work on any programming languages because whitespace indentation is respected.

# Should you use this tool?
- Pros: 
  - It's nice when the structure of the problem at hand matches this kind of "top-down" recursive substitution of code fragments.
  - Can intersperse documentation and comments among code more flexibly than with traditional comments.
- Cons: 
  - You lose all intelli-sense abilities (code completion, syntax highlighting, LSP type checking, refactoring tools). It's just plain text.
  - Development flow now has 1 more stage. Web file has to be tangled, before the output file is then ran through all the normal checks (syntax checkers / type checkers / further compilation with other source code files, etc)
  - Collaboration using line-based version control systems might detect more conflicts.
- Neutral:
  - Traditional programming has the code well-structured, but the explanation of the code fragmented. This makes working with the code easy, but understanding it hard.
  - Literate programming has the explanation of the code well-structured, but the code fragmented. This makes understanding the code easy, but refactoring it hard.


# Usage:
```
python main.py --src_path PWB_SOURCE_FILE [--top_lvl_fragment FRAGMENT_NAME] [--include_src_lineno]
```


# Features & Tutorial mixed tgt
- credits: The idea for which features to implement, and the main explanation of each of the features, is largely copied from the [noweb man pages](https://man.cx/noweb(1)), with some edits where this implementation has different functionality.

- A noweb file is a sequence of chunks, which may appear in any order. A chunk may contain code or documentation. 
- Documentation chunks begin with a line that starts with an at sign (@) followed by a space or newline. They have no names.
- Code chunks begin with `<<chunk name>>=` at the start of a line. If a code chunk is on a line of its own, it's treated as a "multiline" chunk. If some code exists on that same line as the definition, it is treated as an "inline" chunk.
- The double left angle bracket (<<) must be in the first column.
- Chunks are terminated by the beginning of another chunk, or by end of file.
- If the first line in the file does not mark the beginning of a chunk, it is assumed to be the first line of a documentation chunk.
- Documentation chunks are completely ignored when tangling the output.
- Code chunks contain program source code and references to other code chunks.
- Several code chunks may have the same name; noweb concatenates their definitions to produce a single chunk, just as other literate-programming tools do.
- A code-chunk definition is like a macro definition; it contains references to other chunks, which are themselves expanded, and so on. 
- pyweb’s output is readable; it preserves the indentation of expanded chunks with respect to the chunks in which they appear. This is essential when using it for whitespace-significant programming languages (like Python).
- if the `--include_src_lineno` flag is set, pyweb includes line-number information.

# todo:
- detect cyclic code fragment references, bc that will lead to infinite loop and is 100% a bug.
- warn of unused fragments / suggest fragments which are likely to be typos (low edit distance perhaps?)
- issue informative error when referencing undefined code chunk
- allow concatenation to inline chunks?
  - line number information must be omitted for inline-chunks. There's a high probability the output code will not work correctly otherwise, especially since python doesn't have inline comments. This will be possible for languages with inline comments. For e.g., C (/* a comment */)
- line number information is in the form of comments. The comment syntax used is now fixed as Python comments (#). Have this be an input format so it's more flexible.
- for compiler swag, make pyweb "self-hosted"? Meaning implement pyweb using a pyweb src file.
- for better diagnostics, probably make a line class which stores each source line and lineno. Right now i only have lineno as the line a code fragment was defined.
