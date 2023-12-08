print('hi')
# <<multiline block>>, line 13
if False or (True and True):
    # <<Print multiple values>>, line 21
    print("here's a tuple and a dictionary: ", (123, 456), {i:i*i for i in range(20)})
else:
    print('false')
