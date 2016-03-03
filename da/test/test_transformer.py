from da.compiler.ui import *
from da.compiler.dast import DastTransformer

class TestTransformer(DastTransformer):
    def visit_EventHandler(self, node):
        return None

da = dast_from_file("await.da")
