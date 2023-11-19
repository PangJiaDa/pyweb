# <<main>>, line 4
# <<imports>>, line 12
# some random imports i'm not going to use
import sys
import re
import datetime
# <<global function definitions>>, line 20
def plus(a, b):
    return a + b
# line 38
def mult(a, b):
    return a * b
# <<main function>>, line 24
def main():
    # <<main body>>, line 28
    print('please enter 2 numbers, separated by <ENTER>')
    a = int(input())
    b = int(input())
    print(f'the sum is: {plus(a, b)}')
    # line 43
    # showing we can concat to the main body too
    print(f'and the product of the 2 nums is: {mult(a,b)}')
if __name__ == '__main__':
    main()
