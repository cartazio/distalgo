from da.compiler.ui import *
from da.compiler.utils import to_pseudo

prog = """
import sys
"""

dast = daast_from_str(prog)
print(to_pseudo(dast))

dast = daast_from_file("await.da")
print(to_pseudo(dast))
