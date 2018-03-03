#!python
from subprocess import run, PIPE
from sys import stdout, stderr
import os.path


_here = os.path.dirname(os.path.abspath(__file__))
venv_path = os.path.abspath(os.path.join(_here, os.path.pardir, 'venv36'))

print('''
building virtual environment in %s...
''' % venv_path)

rstat = run(['virtualenv', '-v', venv_path], stdout=PIPE, stderr=PIPE, check=True)

print('''
...done building virtual environment
''')
