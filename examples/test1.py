{'*': [CodeFragment(name='*',
                    defn_lineno=8,
                    code_lines=["print('hi')\n", '@<multiline block@>\n'])],
 'Print multiple values': [CodeFragment(name='Print multiple values',
                                        defn_lineno=20,
                                        code_lines=['print(@<inline expr1@>, '
                                                    '@<inline expr2@>, '
                                                    '@<inline expr3@>)\n'])],
 'True condition': [CodeFragment(name='True condition',
                                 defn_lineno=18,
                                 code_lines=[' False or (True and True)\n'])],
 'inline expr1': [CodeFragment(name='inline expr1',
                               defn_lineno=23,
                               code_lines=['       "here\'s a tuple and a '
                                           'dictionary:"\n'])],
 'inline expr2': [CodeFragment(name='inline expr2',
                               defn_lineno=24,
                               code_lines=['        (@<tup1@>, @<tup2@>)\n'])],
 'inline expr3': [CodeFragment(name='inline expr3',
                               defn_lineno=26,
                               code_lines=['{i:i*i for i in range(20)} \n'])],
 'multiline block': [CodeFragment(name='multiline block',
                                  defn_lineno=12,
                                  code_lines=['if @<True condition@>:\n',
                                              '    @<Print multiple values@>\n',
                                              'else:\n',
                                              "    print('false')\n"])],
 'tup1': [CodeFragment(name='tup1', defn_lineno=30, code_lines=[' 123\n'])],
 'tup2': [CodeFragment(name='tup2', defn_lineno=31, code_lines=[' 456\n'])]}
==================== multi-line expansion pass num=1 ====================
<<*>>, line 8
print('hi')
@<multiline block@>
==================== multi-line expansion pass num=2 ====================
<<*>>, line 8
print('hi')
# <<multiline block>>, line 12
if @<True condition@>:
    @<Print multiple values@>
else:
    print('false')
==================== multi-line expansion pass num=3 ====================
<<*>>, line 8
print('hi')
# <<multiline block>>, line 12
if @<True condition@>:
    # <<Print multiple values>>, line 20
    print(@<inline expr1@>, @<inline expr2@>, @<inline expr3@>)
else:
    print('false')
==================== in-line expansion pass num=1 ====================
<<*>>, line 8
print('hi')
# <<multiline block>>, line 12
if @<True condition@>:
    # <<Print multiple values>>, line 20
    print(@<inline expr1@>, @<inline expr2@>, @<inline expr3@>)
else:
    print('false')

==================== in-line expansion pass num=2 ====================
<<*>>, line 8
print('hi')
# <<multiline block>>, line 12
if False or (True and True):
    # <<Print multiple values>>, line 20
    print(@<inline expr1@>, @<inline expr2@>, @<inline expr3@>)
else:
    print('false')

==================== in-line expansion pass num=3 ====================
<<*>>, line 8
print('hi')
# <<multiline block>>, line 12
if False or (True and True):
    # <<Print multiple values>>, line 20
    print("here's a tuple and a dictionary:", @<inline expr2@>, @<inline expr3@>)
else:
    print('false')

==================== in-line expansion pass num=4 ====================
<<*>>, line 8
print('hi')
# <<multiline block>>, line 12
if False or (True and True):
    # <<Print multiple values>>, line 20
    print("here's a tuple and a dictionary:", (@<tup1@>, @<tup2@>), @<inline expr3@>)
else:
    print('false')

==================== in-line expansion pass num=5 ====================
<<*>>, line 8
print('hi')
# <<multiline block>>, line 12
if False or (True and True):
    # <<Print multiple values>>, line 20
    print("here's a tuple and a dictionary:", (123, @<tup2@>), @<inline expr3@>)
else:
    print('false')

==================== in-line expansion pass num=6 ====================
<<*>>, line 8
print('hi')
# <<multiline block>>, line 12
if False or (True and True):
    # <<Print multiple values>>, line 20
    print("here's a tuple and a dictionary:", (123, 456), @<inline expr3@>)
else:
    print('false')

<<*>>, line 8
print('hi')
# <<multiline block>>, line 12
if False or (True and True):
    # <<Print multiple values>>, line 20
    print("here's a tuple and a dictionary:", (123, 456), {i:i*i for i in range(20)})
else:
    print('false')

