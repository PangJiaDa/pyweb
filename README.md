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

# CWEB Manual takeaways:
- maybe use `@<` and `@>` instead? or for inline references specifically?
- for code fragment names matching, it allows references to only be prefixes of the definition


# post-mortem on doing the refactor. Why was i so lost, and what did i do to solve it?
- what was i trying to solve? Allow inline code fragments. So i had to solve inline fragment definitions and referencing.
  - allow defining of multiline code fragments on separate lines. This is just preserving functionality.
  - allow defining of inline code fragments. I wanted some flexibility.
    - have code on the same line as defn or on new line
  - to introduce new syntax to differentiate the two?
    - in the end i didn't
- what were the problems?
  - how to process? pure C style parsing and non-linebased? Or using line-based without regex? Or line-based and with regex? Which stage to handle empty pwb file lines?
  - for those inline code frags, what whitespace to store and how much to trim upon expansion?
    - how much text to store?
      - storing too much whitespace, then how to insert during expansion without messing alignment up?
      - store all whitespace? right_trimmed? left_trimmed? What about difference in whitespace for inline defn on same line vs new line?
    - seems to have different expansion procedures for multiline and inline code frags, which made it hard to think of a general procedure to do both.
      - multiline substitution:
        - the newline after the code fragment would be removed
        - indentation of every line has to be respected
      - inline substutition:
        - the newline after the code fragment would NOT be removed
        - no indentation woes, could just expand the code in place, trimming all surrounding whitespace. Also didn't have to worry about multiline-inline code frags bc i limited the scope for ease of design and impl.
  - allow concatenation of inline frags? 
    - The inline frag could possibly last multiple lines, but it would be super difficult to make the tangle valid python. So i reduced scope: can only do single line inline fragment.
  - just worried about excessive string copying each time. In the end i think i make a whole copy of the output file code basically every expansion pass i make. If the source code file becomes massive, that might become a problem. So perhaps premature optimization made me unable to do the simple solution that worked but could be improved.
  - when to do validation of each part? when processing? when substituting? at the start? Too overwhelming.
- how did i solve each of them?
  - did some iterations thing. As usual, when processing chunks of array, seems helpful to iterate to the start of chunk, spawn another pointer j, and iterate that till after the chunk. That can handle end of array and end of chunk pretty nicely. So the invariant is that j will always point to first index after end of cur chunk. Invariants like those are nice, they're simple enough for me to understand.
  - i think i'm too used to iterating once, no back- or forward-track of iteration, over an iterable. But sometimes i need something more flexible than just a once-through iteration.
  - since i (eventually, unsystematically) realised that multiline expansion and inline expansion were quite different in terms of steps, i broke the expansion into 2 different phases too.
    - the ML pass and IL pass. Then since i alr had the ML pass impl from the existing version, that made the incremental functionality no that much harder for the expansion step.
      - this idea of just doing something (even though not globally optimal), but with each subroutine i write my pen is getting mightier. I may not know how to get from A to Z, but my (wrong) function can get from A to M. And then it's easier to see how to get from M to Z. Then do composition. Even though the overall isn't globally efficient, again. I shouldn't worry about it at this point, even though in the end 99% of the time i'm writing super O(N^2) style code :sad face:
    - Then the expansion i took a super simple "while have at least 1 more to process, process it" approach. Simplest, even though most naieve, but who cares at this point yknow? Premature optimization.
  - using classes to have basically global variables among the set of class methods, but not fully global such that it polluted the scope.
  - used the same repr for ML and IL code frags, but had to use discipline of making sure inline frags were only 1 line long. Then validation (which in the end was only done for inline frags), was done when it was most convenient. In this case that was during inline expansion. Since i didn't care about computational efficiency, i could expand basically the entire source code alr, and in the last inline expansion it could fail. But idc alr.
  - had this eurika moment when i could visualize the code transformation process bc i have just been thinking about it for days. That a code ref is a list of code frags. And each code frag expanded to its (optional) source lineno, and a list of code lines. That process was visualized beautifully for multiline expansion. But i totally scrapped that after i realised that i wasn't applicable to inline expansion / tried to make something that could work for both. In the end specially coded 2 separate functions
- TIL:
  - regex stuff: 
    - .* is performs greedy match
    - .*? performs minimally greedy match
    - this is relevant if i'm matching `<.*>` vs `<.*?>` in the string `<A> <B> <C> <D> <E>`, where i should pair up the minimal of stuff between openning and closing brackets, instead of the max number of things, which would enclose nested brackets entirely.
  - this idea of just inch closer to the solution one step. Then while not done, inch closer. It might not be the most efficient, but seems like whenever i'm stuck, i just process 1 thing. Then iterate to process any number of things. Then abstract that away to process 1 series of things. Then iterate to process any number of series of things, until the problem is solved.
    - multiline expansion: just expand 1 ML code frag ref at a time.
    - inline expansion: just expand the 1st IL code frag ref in the src. And copy the whole source rip.