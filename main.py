import sys
import re
import click
from pathlib import Path
from pprint import pprint
from dataclasses import dataclass


@dataclass
class CodeFragment:
    name: str
    lineno: int
    source_lines: list[str]


IR = dict[str, list[CodeFragment]]


CODE_FRAGMENT_REFERENCE_RE = re.compile(
    r'(?P<leading_whitespace>\s*)<<(?P<fragment_name>.*)>>')
CODE_FRAGMENT_DEFN_RE = re.compile(
    r'<<(?P<fragment_name>.*)>>=')


def flush_code_fragment(fragment_map: IR, cur_source_lines: list[str], cur_frag_name: str, frag_line_start: int) -> None:
    "Mutates ir."
    if cur_source_lines:
        if cur_frag_name not in fragment_map:
            fragment_map[cur_frag_name] = []
        fragment_map[cur_frag_name].append(CodeFragment(
            name=cur_frag_name,
            lineno=frag_line_start,
            source_lines=cur_source_lines
        ))


def extract_IR(src_path: Path) -> IR:
    with open(src_path, 'r') as src_file:
        lines = src_file.readlines()
        # if src file ends with a code block, we have to explicitly flush that block to output. But if we append the start of a fake block at the end, that will implicitly flush the last code block when it's encountered.
        lines.append('@')

    fragment_map: IR = {}

    in_code_mode: bool = False
    cur_frag_name: str = ''
    cur_source_lines: list[str] = []
    frag_line_start: int = -1
    # get some numbered lines
    for lineno, line in enumerate(lines):
        lineno = lineno + 1  # want 1-indexed lines
        if line.strip() == '':  # ignore empty lines
            continue
        line = line.rstrip()
        frag_defn_m = CODE_FRAGMENT_DEFN_RE.match(line)
        # if it's the start of a new block of anytype, dump the previous fragment, if there was any
        if in_code_mode and (line.strip() == '@' or frag_defn_m):
            flush_code_fragment(fragment_map, cur_source_lines,
                                cur_frag_name, frag_line_start)
            # print(f'at line {lineno} appended {cur_frag_name}')

        # now match on line type
        if line.strip() == '@':  # start of documentation block
            in_code_mode = False
        elif frag_defn_m:
            # start of code block
            # get ready to store subsequent lines into this code fragment
            in_code_mode = True
            cur_frag_name = frag_defn_m.group('fragment_name')
            frag_line_start = lineno
            cur_source_lines = []
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


def print_fragment(ir: IR, fragment_name: str, indentation: str = '') -> None:
    "Print this fragment, with every line indented by `indentation`."
    fragments = ir[fragment_name]
    for i, frag in enumerate(fragments):
        # for the first of all the same-named fragments, I want to print the fragment name as a comment. Encourages descriptive fragment names
        if i == 0:
            print(f'{indentation}# <<{frag.name}>>, line {frag.lineno}')
        else:
            print(f'{indentation}# line {frag.lineno}')

        for line in frag.source_lines:
            m = CODE_FRAGMENT_REFERENCE_RE.match(line)
            if m:
                # it's a code reference. Indent the referenced block by there amount of whitespace the reference has, plus the amount of leading whitespace the enclosing block has.
                print_fragment(ir, m.group('fragment_name'),
                               m.group('leading_whitespace')+indentation)
            else:
                # normal line
                print(f'{indentation}{line}')


@click.command()
@click.option('--src_path', '-s', help='Path to the pyweb source file to tangle')
@click.option('--top_lvl_fragment', '-f', help='Name of the fragment to expand. Typically this is the top level fragment that expands to the whole tangled source file.')
def tangle(src_path: Path, top_lvl_fragment: str) -> None:
    "Prints the tangled source code to stdout. Redirect it into a file yourself."
    src_path = Path('.').resolve() / src_path
    ir = extract_IR(src_path)
    print_fragment(ir, top_lvl_fragment)


if __name__ == '__main__':
    tangle()
