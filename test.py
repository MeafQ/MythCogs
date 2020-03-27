from datetime import timedelta

def f(): timedelta(minutes=15) - timedelta(seconds=15)
def g(): timedelta(minutes=15).total_seconds() - 15
#def h(): 42
from timeit import timeit
print(timeit(f))
print(timeit(g))
#print(timeit(h))