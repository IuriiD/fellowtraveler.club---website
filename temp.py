test = ['hello', {'myname': 1}]

print(test)
for i in test:
    if 'myname' in i:
        test.remove(i)
print(test)