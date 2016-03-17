from da.compiler.ui import *
from da.compiler.utils import to_pseudo
from da.compiler.dast import DastTransformer
import da.compiler.dast as dast

class RemoveEventHandlerTransformer(DastTransformer):
    def visit_EventHandler(self, node):
        return None

ast = daast_from_file("await.da")
print(to_pseudo(RemoveEventHandlerTransformer().visit(ast)))

class MangleProcessStateTransformer(DastTransformer):
    def __init__(self):
        super().__init__()
        self.visited = set()
    def visit_NamedVar(self, node):
        if node not in self.visited and isinstance(node.scope, dast.Process):
            node.name = "___" + node.name
            self.visited.add(node)
        return node

print(to_pseudo(MangleProcessStateTransformer().visit(ast)))
