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
    lineno: int
    # for multiline code fragment
    source_lines: list[str]
    # for inline code fragment.
    # code smell... this thing can't handle both types of code frag well.
    is_inline: bool
    source_text: str

    @staticmethod
    def make_multiline_fragment(name: str, lineno: int, source_lines: list[str]) -> CodeFragment:
        return CodeFragment(
            name=name,
            lineno=lineno,
            source_lines=source_lines,
            is_inline=False,
            source_text=''
        )

    @staticmethod
    def make_inline_fragment(name: str, lineno: int, source_text: str) -> CodeFragment:
        return CodeFragment(
            name=name,
            lineno=lineno,
            source_lines=[],
            is_inline=True,
            source_text=source_text
        )


IR = dict[str, list[CodeFragment]]


CODE_FRAGMENT_REFERENCE_RE = re.compile(
    r'(?P<leading_whitespace>\s*)<<(?P<fragment_name>.*)>>')
CODE_FRAGMENT_DEFN_RE = re.compile(
    r'<<(?P<fragment_name>.*)>>=(?P<trailing_code>.*\n)')


def flush_code_fragment(fragment_map: IR, frag_defn_match: re.Match[Any], source_lines: list[str], lineno: int) -> None:
    "Mutates ir."
    frag_name = frag_defn_match.group('fragment_name')
    if frag_name not in fragment_map:
        fragment_map[frag_name] = []

    trailing_code = frag_defn_match.group('trailing_code')
    is_inline_fragment = not trailing_code.isspace()
    if is_inline_fragment:
        fragment_map[frag_name].append(CodeFragment.make_inline_fragment(
            lineno=lineno,
            name=frag_name,
            source_text=trailing_code.strip()
        ))
    else:
        # multiline fragment
        fragment_map[frag_name].append(CodeFragment.make_multiline_fragment(
            lineno=lineno,
            name=frag_name,
            source_lines=source_lines,
        ))


def extract_IR(src_path: Path) -> IR:
    with open(src_path, 'r') as src_file:
        lines = src_file.readlines()
        # if src file ends with a code block, we have to explicitly flush that block to output. But if we append the start of a fake block at the end, that will implicitly flush the last code block when it's encountered.
        lines.append('@\n')

    fragment_map: IR = {}

    in_code_mode: bool = False
    cur_source_lines: list[str] = []
    frag_line_start: int = -1
    # we'll handle this such that it should never be None
    frag_defn_match_saved: re.Match[Any] | None = None
    # get some numbered lines
    for lineno, line in enumerate(lines):
        lineno = lineno + 1  # want 1-indexed lines
        if line.strip() == '':  # ignore empty lines
            continue
        frag_defn_match = CODE_FRAGMENT_DEFN_RE.match(line)
        lstripped = line.lstrip()
        # this line should at least be 2 chars long.
        is_start_of_doc_chunk = lstripped[0] == '@' and lstripped[1].isspace()
        # if it's the start of a new block of anytype, dump the previous fragment, if there was any
        if in_code_mode and (is_start_of_doc_chunk or frag_defn_match):
            assert frag_defn_match_saved is not None  # mypy
            flush_code_fragment(fragment_map, frag_defn_match_saved,
                                cur_source_lines, frag_line_start)

        # now match on line type
        # start of documentation block
        if is_start_of_doc_chunk:
            in_code_mode = False
        elif frag_defn_match:
            # start of code block
            # get ready to store subsequent lines into this code fragment
            in_code_mode = True
            frag_line_start = lineno
            cur_source_lines = []
            assert frag_defn_match is not None  # mypy
            frag_defn_match_saved = frag_defn_match
        else:
            # a line that doesn't change the code block mode. Process it according to the current block mode.
            if in_code_mode:
                cur_source_lines.append(line)
            else:
                # we discard everything that isn't code, bc we are only interested in tangling.
                pass
    # pprint(fragment_map)
    # print('-' * 30)
    return fragment_map


def rec_expand_inline_ref(ir: IR, line: str) -> str:
    """
    Validate the string while I'm at it.
    """
    # wait i just realised... << is the bitshift operator in python... meaning i can't use bit shifts in my python programs (facepalm)
    pos = 0
    res = []
    while True:
        si = line[pos:].find('<<')
        ei = line[pos:].find('>>')
        if si == -1:
            break
        if ei == -1:  # implicit: si != -1
            assert False, f'Couldn\'t find matching closing >> in {line=}'
        res.append(line[pos:pos+si])
        inline_frag_name = line[pos+si+2:pos+ei]
        inline_frags = ir[inline_frag_name]
        assert len(
            inline_frags) == 1, f'suspicious, inline frag has multiple fragments {inline_frags}'
        res.append(rec_expand_inline_ref(ir, inline_frags[0].source_text))
        pos = pos+ei+2
    # process rest of pos?
    res.append(line[pos:])
    return ''.join(res)


def print_fragment(ir: IR, fragment_name: str, indentation: str = '', include_src_lineno: bool = True) -> None:
    "Print this fragment, with every line indented by `indentation`."
    fragments = ir[fragment_name]
    for i, frag in enumerate(fragments):
        # for the first of all the same-named fragments, I want to print the fragment name as a comment. Encourages descriptive fragment names, but only if it's a multiline fragment.
        if include_src_lineno and not frag.is_inline:
            if i == 0:
                print(f'{indentation}# <<{frag.name}>>, line {frag.lineno}')
            else:
                print(f'{indentation}# line {frag.lineno}')

        for line in frag.source_lines:
            # could have multiple inline fragment references.
            # Find them all and recursively substitute them
            multiline_ref_match = CODE_FRAGMENT_REFERENCE_RE.match(line)
            if multiline_ref_match:
                # it's a code reference. Indent the referenced block by there amount of whitespace the reference has, plus the amount of leading whitespace the enclosing block has.
                print_fragment(ir=ir,
                               fragment_name=multiline_ref_match.group('fragment_name'),
                               indentation=multiline_ref_match.group('leading_whitespace')+indentation,
                               include_src_lineno=include_src_lineno)
            else:
                print(f'{indentation}{rec_expand_inline_ref(ir, line)}',end='')


@click.command()
@click.option('--src_path', '-s', help='Path to the pyweb source file to tangle', show_default=True)
@click.option('--top_lvl_fragment', '-f', help='Name of the fragment to expand. Typically this is the top level fragment that expands to the whole tangled source file.', default='*', show_default=True)
@click.option('--include_src_lineno', '-L', is_flag=True, help='In the output file, include comments showing the line in the pyweb file the chunk being expanded was defined.', default=False, show_default=True)
def tangle(src_path: Path, top_lvl_fragment: str, include_src_lineno: bool) -> None:
    "Prints the tangled source code to stdout. Typically, stdout is redirected into a source code file."
    src_path = Path('.').resolve() / src_path
    ir = extract_IR(src_path)
    print_fragment(ir=ir,
                   fragment_name=top_lvl_fragment,
                   include_src_lineno=include_src_lineno)


if __name__ == '__main__':
    tangle()
