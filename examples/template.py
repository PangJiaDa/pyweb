{'global function definitions': [CodeFragment(name='global function '
                                                   'definitions',
                                              defn_lineno=19,
                                              code_lines=['def plus(a, b):\n',
                                                          '    return a + b\n']),
                                 CodeFragment(name='global function '
                                                   'definitions',
                                              defn_lineno=37,
                                              code_lines=['def mult(a, b):\n',
                                                          '    return a * '
                                                          'b\n'])],
 'imports': [CodeFragment(name='imports',
                          defn_lineno=11,
                          code_lines=["# some random imports i'm not going to "
                                      'use\n',
                                      'import sys\n',
                                      'import re\n',
                                      'import datetime\n'])],
 'main': [CodeFragment(name='main',
                       defn_lineno=3,
                       code_lines=['@<imports@>\n',
                                   '@<global function definitions@>\n',
                                   '@<main function@>\n',
                                   "if __name__ == '__main__':\n",
                                   '    main()\n'])],
 'main body': [CodeFragment(name='main body',
                            defn_lineno=27,
                            code_lines=["print('please enter 2 numbers, "
                                        "separated by <ENTER>')\n",
                                        'a = int(input())\n',
                                        'b = int(input())\n',
                                        "print(f'the sum is: {plus(a, b)}')\n"]),
               CodeFragment(name='main body',
                            defn_lineno=42,
                            code_lines=['# showing we can concat to the main '
                                        'body too\n',
                                        "print(f'and the product of the 2 nums "
                                        "is: {mult(a,b)}')\n"])],
 'main function': [CodeFragment(name='main function',
                                defn_lineno=23,
                                code_lines=['def main():\n',
                                            '    @<main body@>\n'])]}
==================== multi-line expansion pass num=1 ====================
@<imports@>
@<global function definitions@>
@<main function@>
if __name__ == '__main__':
    main()
==================== multi-line expansion pass num=2 ====================
# some random imports i'm not going to use
import sys
import re
import datetime
def plus(a, b):
    return a + b
def mult(a, b):
    return a * b
def main():
    @<main body@>
if __name__ == '__main__':
    main()
==================== multi-line expansion pass num=3 ====================
# some random imports i'm not going to use
import sys
import re
import datetime
def plus(a, b):
    return a + b
def mult(a, b):
    return a * b
def main():
    print('please enter 2 numbers, separated by <ENTER>')
    a = int(input())
    b = int(input())
    print(f'the sum is: {plus(a, b)}')
    # showing we can concat to the main body too
    print(f'and the product of the 2 nums is: {mult(a,b)}')
if __name__ == '__main__':
    main()
# some random imports i'm not going to use
import sys
import re
import datetime
def plus(a, b):
    return a + b
def mult(a, b):
    return a * b
def main():
    print('please enter 2 numbers, separated by <ENTER>')
    a = int(input())
    b = int(input())
    print(f'the sum is: {plus(a, b)}')
    # showing we can concat to the main body too
    print(f'and the product of the 2 nums is: {mult(a,b)}')
if __name__ == '__main__':
    main()

