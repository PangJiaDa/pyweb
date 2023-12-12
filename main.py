from __future__ import annotations

import sys
import re
from typing import Any
import click
import logging
from pathlib import Path
from pprint import pprint, pformat
from dataclasses import dataclass

DEBUG: bool = False


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
        r'@<(?P<fragment_name>.*?)@>=(?P<trailing_text>.*)$')
    CODE_FRAGMENT_MULTILINE_REFERENCE_RE = re.compile(
        r'(?P<leading_whitespace>\s*)@<(?P<fragment_name>.*?)@>')
    # CODE_FRAGMENT_INLINE_REFERENCE_RE = re.compile(
    # r'@<(?P<fragment_name>.*)@>')

    def __init__(self, src_path: Path) -> None:
        self.src_path: Path = src_path
        self.fragment_map: IR = {}
        # dict of frag_name to expanded code line
        self.inline_fragment_expansion_cache: dict[str, str] = {}
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
                trailing_text = match.group('trailing_text')
                # trailing_text.isspace() is False for the empty string...
                if trailing_text.strip() != '':
                    # inline code frag defn
                    # save it with all the surrounding whitespace
                    code_lines.append(trailing_text)

                # lines[i+1:j] are source lines belonging to this chunk, including empty lines
                # omit them
                code_lines.extend(
                    ln for ln in lines[i+1:j] if ln.strip() != '')

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
        # keep expanding lines in the output lines if they are multiline code references. So start with a single reference to the root fragment.
        out_lines: list[str] = [f'@<{root_fragment}@>']
        next_out_lines: list[str] = []

        pass_number = 1

        another_pass: bool = True
        while another_pass:
            another_pass = False

            if DEBUG:
                print()
                print(
                    f'{"="*20} multi-line expansion pass num={pass_number} {"="*20}')
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
                        # maybe print line number relating to this fragment
                        if include_source_lineno:
                            next_out_lines.append(
                                indentation + '# ' + ('' if i != 0 else f'<<{frag.name}>>, ') + f'line {frag.defn_lineno}\n')
                        for expanded_line in frag.code_lines:
                            # tricky: every line in the expanded fragment must be indented by the indentation of the enclosing fragment.
                            next_out_lines.append(indentation+expanded_line)
            out_lines = next_out_lines
            next_out_lines = []
        return ''.join(out_lines)

    def expand_inline_code_ref(self, frag_name: str) -> str:
        """
        Primarily intended for performance improvements. It caches what an inline code fragment should expand to.
        Must do recursive expansion of this fragment. And only cache the fully expanded code_text.
        Also does some validation.
        """
        if frag_name in self.inline_fragment_expansion_cache:
            return self.inline_fragment_expansion_cache[frag_name]

        frags = self.fragment_map[frag_name]
        assert len(
            frags) == 1, f'inline reference {frag_name} shouldn\'t have more than 1 fragment definition:\n{pformat(frags)}'
        frag = frags[0]
        code_lines = frag.code_lines
        assert len(
            code_lines) == 1, f'inline reference {frag_name} shouldn\'t have more than 1 line of code:\n{pformat(code_lines)}'
        # return it without any whitespace
        code_line = code_lines[0].strip()
        # this code_line could have other inline expansions within it. Recursively expand them (caching along the way), and return the code_text fully expanded.

        def find_all(string: str, substr: str) -> list[int]:
            "Like string.find(), but finds all occurances. Returns empty list if no occurances found."
            idx = string.find(substr)
            ans = []
            while idx != -1:
                ans.append(idx)
                idx = string.find(substr, ans[-1]+1)
            return ans

        # start and end indices
        sids = find_all(code_line, '@<')
        eids = find_all(code_line, '@>')
        # TODO: this can be done much more elegantly with regexes. Find all. It should have a span. The replace all refs with f string templates. And then f string format it back.
        assert len(sids) == len(
            eids), f'not matching number of opening and closing inline code fragments detected: {sids} opens and {eids} closes'

        if not sids:
            # nothing further to expand
            self.inline_fragment_expansion_cache[frag_name] = code_line
            return code_line

        # must expand some more inline code refs
        for sid, eid in zip(sids, eids):
            assert sid < eid, f'opening inline code tag after closing tag: starts={sids}, ends={eids}, {sid}>{eid}'
        all_frag_refs = [code_line[si+2:ei] for si, ei in zip(sids, eids)]
        expanded_frags = [self.expand_inline_code_ref(
            ref) for ref in all_frag_refs]
        # put in the bit before 1st match, then put in pairs of expanded part and bit between expansions.
        parts: list[str] = [code_line[:sids[0]]]
        for i in range(len(sids)):
            parts.append(expanded_frags[i])  # code expansion
            # between expansions, after
            between = code_line[eids[i]+2:] if i == len(
                sids) - 1 else code_line[eids[i]+2:sids[i+1]]
            parts.append(between)
        expanded_line = ''.join(parts)

        self.inline_fragment_expansion_cache[frag_name] = expanded_line
        return expanded_line

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
            if DEBUG:
                print(f'{"="*20} in-line expansion pass num={pass_number} {"="*20}')
                print(source_code)
                pass_number += 1

            frag_name = source_code[si+2:ei]
            code_line = self.expand_inline_code_ref(frag_name)
            source_code = source_code[:si] + code_line + source_code[ei+2:]
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
@click.option('--debug', '-d', is_flag=True, default=False, show_default=True, help='Prints out code at every code fragment expansion.')
def tangle(src_path: Path, top_lvl_fragment: str, include_src_lineno: bool, debug: bool) -> None:
    "Prints the tangled source code to stdout. Typically, stdout is redirected into a source code file."
    global DEBUG
    DEBUG = debug

    src_path = Path('.').resolve() / src_path
    pyweb = PyWeb(src_path)
    if DEBUG:
        pprint(pyweb.fragment_map)

    tangled_src = pyweb.tangle(
        root_fragment=top_lvl_fragment, include_source_lineno=include_src_lineno)
    if DEBUG:
        print()
        print(f'{"="*20} Final Tangled Output {"="*20}')
    print(tangled_src)


if __name__ == '__main__':
    tangle()
