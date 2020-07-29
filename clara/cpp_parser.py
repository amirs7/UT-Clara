from pycparser.c_ast import ID

from .c_parser import CParser
from .model import Op, Var, VAR_OUT, Const, VAR_IN
from .parser import addlangparser


class CppParser(CParser):

    def __init__(self, *args, **kwargs):
        super(CppParser, self).__init__(*args, **kwargs)
        self.postincdec = 0

        self.inswitch = False

        self.fncdef = False

    def visit_cout(self, node):
        expr = Op('StrAppend', Var(VAR_OUT),
                  self.visit_expr(node.right),
                  line=node.coord.line)
        self.addexpr(VAR_OUT, expr)
        return Var(VAR_OUT)

    def visit_cin(self, node):
        right = self.visit_expr(node.right)
        expression = Op('ListHead', Const('*'), Var(VAR_IN), line=node.coord.line)
        if isinstance(right, Var):
            self.addexpr(right.name, expression)
        self.addexpr(VAR_IN, Op('ListTail', Var(VAR_IN), line=node.coord.line))
        return Var(VAR_IN)

    def visit_BinaryOp(self, node):
        if node.op == '<<':
            left = self.visit_expr(node.left)
            if isinstance(left, Var) and (left.name == 'cout' or left.name == VAR_OUT):
                return self.visit_cout(node)
        elif node.op == '>>':
            left = self.visit_expr(node.left)
            if isinstance(left, Var) and (left.name == 'cin' or left.name == VAR_IN):
                return self.visit_cin(node)
        else:
            return super().visit_BinaryOp(node)


addlangparser('cpp', CppParser)
