# PYWEB
Macro expansion system, mostly copying literate programming ideas and especially the [noweb](https://www.cs.tufts.edu/~nr/noweb/) tool.
Should work on any programming languages because whitespace indentation is respected.

# PYWEB file extension
file.pwb

# Syntax introduced
`@`: on its own line starts a comment block, which lasts until start of the next comment / code block
`<<fragment name>>`: references a code block. Can refer to blocks before their creation
`<<fragment name>>=`: on its own line starts a code block, which lasts until start of the next comment / code block. Repeated uses of this throughout the program will just concatenate those code fragments with the same identifier at the same indentation level.

# Challenges
One challenge of python is that whitespace is significant. So I can't tangle an absolute garbage mess. Indentation must be respected for it to be a valid (and intended) python program.
So indentation of code fragments is significant. Starting `<<frag>>` with leading whitespaces or not will affect whether that entire fragment is indented by that amount of whitespace.

# Should you use this tool?
- Pros: it's nice when the structure of the problem at hand matches this kind of "top-down" recursive substitution of code fragments.
- Cons: You lose all intelli-sense and code completion abilities.

# Features
- just the tangle program
- tangled source code should have some # line: 99 references back to the pyweb source code for slightly easier correlation of pyweb source to tangled source.
- all empty lines in the source code are just omitted. Feel free to space out the program however much you like.
- fragment references should be indented to the level such that the fragment definitions are always at 0 indentation.

# Usage:
- python main.py [PWB_SOURCE_FILE] [FRAGMENT_NAME] > [OUTFILE]

# todo:
- detect cyclic code fragment references, bc that will lead to infinite loop and is 100% a bug.
- warn of unused fragments / suggest fragments which are likely to be typos (low edit distance perhaps?)