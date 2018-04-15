#!python
import os.path
from time import time
from subprocess import run, PIPE
from sys import stdout


_here = os.path.dirname(os.path.abspath(__file__))
venv_path = os.path.abspath(os.path.join(_here, os.path.pardir, 'venv36'))

if __name__ == "__main__":
    print('''
building virtual environment in %s...
''' % venv_path)
    stdout.flush()
    _t0 = time()
    rstat = run(['virtualenv', '-v', venv_path], stdout=PIPE, stderr=PIPE)#, check=True)
    _t1 = time()
    print('''
...done building virtual environment (took %s seconds)
''' % (_t1 - _t0))
