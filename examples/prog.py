# <<main>>, line 4
x = 6
if x <= 5:
    # block is indented
    # <<true block>>, line 18
    print('in true block')
else:
    # <<false block>>, line 21
    print('in false block. I want another indented block below me')
    # <<while loop for 5 times>>, line 28
    for x in range(5):
        print(x)
# line 12
print('just appending same named fragments tgt')
