from da.compiler.parser import *
from da.compiler.pseudo import to_pseudo

prog = """
import sys
"""

dast = daast_from_str(prog)
print(to_pseudo(dast))

dast = daast_from_file("await.da")
print(to_pseudo(dast))
