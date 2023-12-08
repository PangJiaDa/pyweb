from __future__ import annotations

import sys
import re
from typing import Any
import click
import logging
from pathlib import Path
from pprint import pprint
from dataclasses import dataclass


@dataclass
class CodeFragment:
    name: str
    defn_lineno: int
    code_lines: list[str]

    # @staticmethod
    # def make_multiline_fragment(name: str, lineno: int, source_lines: list[str]) -> CodeFragment:
    #     return CodeFragment(
    #         name=name,
    #         lineno=lineno,
    #         source_lines=source_lines,
    #         is_inline=False,
    #         source_text=''
    #     )

    # @staticmethod
    # def make_inline_fragment(name: str, lineno: int, source_text: str) -> CodeFragment:
    #     return CodeFragment(
    #         name=name,
    #         lineno=lineno,
    #         source_lines=[],
    #         is_inline=True,
    #         source_text=source_text
    #     )


IR = dict[str, list[CodeFragment]]


class PyWeb:
    CODE_FRAGMENT_DEFN_RE = re.compile(
        r'@<(?P<fragment_name>.*?)@>=(?P<trailing_text>.*\n)')
    CODE_FRAGMENT_MULTILINE_REFERENCE_RE = re.compile(
        r'(?P<leading_whitespace>\s*)@<(?P<fragment_name>.*?)@>')
    # CODE_FRAGMENT_INLINE_REFERENCE_RE = re.compile(
    # r'@<(?P<fragment_name>.*)@>')

    def __init__(self, src_path: Path) -> None:
        self.src_path: Path = src_path
        self.fragment_map: IR = {}
        self.process()

    def process(self) -> None:
        """
        Few types of lines we might encounter:
        - start of doc chunk only lines: '@\s'
        - start of doc chunk with comments on same line: '@\s hvkjzxchvjkhkzxcjhv'
        - start of code chunk only: '@<abc@>=\s'
        - start of code chunk with code on same line: '@<abc@>=\s*codehehe'
        - normal lines, interpreted differently based on whether we are in a doc or code chunk.

        Both types of doc chunks: we still don't care. Just omit.
        Both types of code chunks: 
            - multiline ones: just append to source_lines
            - inline ones: just append the inline stuff to source_lines too. Later during expansion we do some checking that it can only be 1 line maybe

        Expansion/substitution phase:
        - proceed in 2 stages? All multiline expansion, then all inline expansion? Don't do both at the same time.
        """
        with open(self.src_path) as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i]
            L = len(line)
            assert L >= 1, f'readlines() shouldn\'t return lines this short {line=}'

            if L == 1:
                assert lines[
                    0] == '\n', f'length 1 line should only be the newline char: {lines[0]}'
                # skip empty source lines
                i += 1
            elif PyWeb.is_start_of_doc_chunk(line):
                # start of document chunk.
                # process (by that I mean we ignore it) until the end of the chunk.
                j = i + 1
                # increment j to the lowest index such that it doesn't point to lines from this same chunk. Could be start of new chunk of index out of bounds.
                while j < len(lines) and not PyWeb.is_start_of_new_chunk(lines[j]):
                    j += 1
                # lines[i:j] are the lines of src file that are this same chunk
                # ignore by just incrementing line ptr i
                i = j
            elif PyWeb.is_start_of_code_chunk(line):
                # start of code chunk
                j = i + 1
                while j < len(lines) and not PyWeb.is_start_of_new_chunk(lines[j]):
                    j += 1
                # lines[i:j] are the lines of src file that are this same chunk.
                # Make a code fragment from it.
                # i is pointing to code frag defn line, and maybe inline defn
                # It could be inline or multiline code fragment. FInd out which.
                match = PyWeb.CODE_FRAGMENT_DEFN_RE.match(line)
                assert match is not None, f'line should be start of code fragment, but doesn\'t match code fragment defn regex {line=}'
                code_lines: list[str] = []
                if not match.group('trailing_text').isspace():
                    # inline code frag defn
                    # save it with all the surrounding whitespace
                    code_lines.append(match.group('trailing_text'))

                # lines[i+1:j] are source lines belonging to this chunk, including empty lines
                # omit them
                code_lines.extend(
                    ln for ln in lines[i+1:j] if not ln.isspace())

                self.insert_code_fragment(CodeFragment(
                    name=match.group('fragment_name'),
                    defn_lineno=i,
                    code_lines=code_lines,
                ))

                # next line to process would be j-th line
                i = j

    def insert_code_fragment(self, code_fragment: CodeFragment) -> None:
        frag_name = code_fragment.name
        if frag_name not in self.fragment_map:
            self.fragment_map[frag_name] = []

        self.fragment_map[frag_name].append(code_fragment)

    @staticmethod
    def is_start_of_doc_chunk(line: str) -> bool:
        return line[0] == '@' and line[1].isspace()

    @staticmethod
    def is_start_of_code_chunk(line: str) -> bool:
        "Must check for that trailing @>=, bc normal code frag references would have a leading @< too."
        return PyWeb.CODE_FRAGMENT_DEFN_RE.match(line) is not None

    @staticmethod
    def is_start_of_new_chunk(line: str) -> bool:
        return PyWeb.is_start_of_code_chunk(line) or PyWeb.is_start_of_doc_chunk(line)

    def multiline_expand(self, root_fragment: str, include_source_lineno: bool = True) -> str:
        # output lines of source code
        out_lines: list[str] = []
        next_out_lines: list[str] = []
        frags = self.fragment_map[root_fragment]
        for i, frag in enumerate(frags):
            if include_source_lineno:
                next_out_lines.append(
                    '# ' + ('' if i != 0 else f'<<{frag.name}>>, ') + f'line {frag.defn_lineno}')
            for line in frag.code_lines:
                out_lines.append(line)

        pass_number = 1

        another_pass: bool = True
        while another_pass:
            another_pass = False

            print(f'{"="*20} multi-line expansion pass num={pass_number} {"="*20}')
            [print(ln, end='') for ln in out_lines]
            pass_number += 1

            for line in out_lines:
                match = PyWeb.CODE_FRAGMENT_MULTILINE_REFERENCE_RE.match(line)
                if match is None:
                    next_out_lines.append(line)
                else:
                    # perform expansion
                    # found at least 1 multiline code ref that needed expansion. Have to go another round of substitution bc this might introduce another fragment reference.
                    another_pass = True
                    frag_name = match.group('fragment_name')
                    indentation = match.group('leading_whitespace')
                    for i, frag in enumerate(self.fragment_map[frag_name]):
                        if include_source_lineno:
                            next_out_lines.append(
                                indentation + '# ' + ('' if i != 0 else f'<<{frag.name}>>, ') + f'line {frag.defn_lineno}')
                        for expanded_line in frag.code_lines:
                            # tricky: every line in the expanded fragment must be indented by the indentation of the enclosing fragment.
                            next_out_lines.append(indentation+expanded_line)
            out_lines = next_out_lines
            next_out_lines = []
        return ''.join(out_lines)

    def inline_expand(self, source_code: str) -> str:
        def inline_tag_helper(src: str) -> tuple[int, int]:
            """
            Makes sure the indices of inline code ref tags are 'proper', or returns magic value to say none could be found.
            Raises exceptions when tags are not valid.
            Returns tuple of (start_index, end_index) of the opening and closing tags. Or (-1, -1) if neither exist.
            """
            si = src.find('@<')
            ei = src.find('@>')
            if si == -1 and ei == -1:
                # no more inline expansions
                return (si, ei)
            if si != -1 and ei == -1:
                raise ValueError(
                    f'Found opening inline reference tag at position {si=}, but no matching closing tag.')
            if si == -1 and ei != -1:
                raise ValueError(
                    f'Found closing inline reference tag at position {ei=}, but no matching opening tag.')
            if si > ei:
                raise ValueError(
                    f'Opening inline reference tag found after closing tag {si=} > {ei=}')
            return (si, ei)

        si, ei = inline_tag_helper(source_code)
        pass_number: int = 1
        while si != -1 and ei != -1:
            print(f'{"="*20} in-line expansion pass num={pass_number} {"="*20}')
            print(source_code)
            pass_number += 1

            frag_name = source_code[si+2:ei]
            frags = self.fragment_map[frag_name]
            assert len(
                frags) == 1, f'inline reference {frag_name} shouldn\'t have more than 1 fragment definition.'
            frag = frags[0]
            code_lines = frag.code_lines
            assert len(
                code_lines) == 1, f'inline reference {frag_name} shouldn\'t have more than 1 line of code.'
            code_line = code_lines[0]
            # insert it without any whitespace
            source_code = source_code[:si] + \
                code_line.strip() + source_code[ei+2:]
            si, ei = inline_tag_helper(source_code)
        return source_code

    def tangle(self, root_fragment: str, include_source_lineno: bool = True) -> str:
        multiline_expanded: str = self.multiline_expand(
            root_fragment, include_source_lineno)
        final_source: str = self.inline_expand(multiline_expanded)
        return final_source


@click.command()
@click.option('--src_path', '-s', help='Path to the pyweb source file to tangle')
@click.option('--top_lvl_fragment', '-f', default='*', show_default=True, help='Name of the fragment to expand. Typically this is the top level fragment that expands to the whole tangled source file.')
@click.option('--include_src_lineno', '-L', is_flag=True, default=False, show_default=True, help='In the output file, include comments showing the line in the pyweb file the chunk being expanded was defined.')
def tangle(src_path: Path, top_lvl_fragment: str, include_src_lineno: bool) -> None:
    "Prints the tangled source code to stdout. Typically, stdout is redirected into a source code file."
    src_path = Path('.').resolve() / src_path
    pyweb = PyWeb(src_path)
    pprint(pyweb.fragment_map)
    print(pyweb.tangle(root_fragment=top_lvl_fragment,
          include_source_lineno=include_src_lineno))


if __name__ == '__main__':
    tangle()
