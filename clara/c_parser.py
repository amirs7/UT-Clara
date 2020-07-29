'''
C parser
'''

# Python imports
import re

from subprocess import Popen, PIPE

# clara.py lib imports
from .model import Var, Const, Op, Expr, VAR_IN, VAR_OUT, VAR_RET
from .parser import Parser, ParseError, addlangparser, NotSupported, ParseError

# Parser imports
from pycparser import c_ast, c_parser, plyparser


class CParser(Parser):
    TYPE_SYNONYMS = {
        'double': 'float',
        'long_long_int': 'int',
        'long_int': 'int',
        'long': 'int',
        'unsigned': 'int',
        'unsigned_int': 'int',
        'unsigned_long_int': 'int',
        'unsigned_long': 'int',
    }

    CONSTS = set(['EOF', 'endl'])
    NOTOP = '!'
    OROP = '||'
    ANDOP = '&&'

    LIB_FNCS = set([
        'floor', 'ceil', 'pow', 'abs', 'sqrt', 'log2', 'log10', 'log', 'exp'
    ])

    def __init__(self, *args, **kwargs):
        super(CParser, self).__init__(*args, **kwargs)

        self.postincdec = 0

        self.inswitch = False

        self.fncdef = False

    def pre_process(self, code):
        if re.findall(r'^\s*//\s+#incorrect\s*', code, flags=re.M):
            self.prog.addmeta('incorrect', True)
        mfeed = re.findall(r'^\s*//\s+#feedback\s+(.*)', code, flags=re.M)
        if mfeed:
            self.prog.addmeta('feedback', mfeed[0])

        # Remove includes
        code = re.sub(r'\s*#include.*', ' ', code)

        code = re.sub(r'.*using\s*namespace.*', '', code)

        code = re.sub(r'//.*', '', code)
        code = re.sub(r'/\*.*\*/', '', code)

        # Run CPP
        # args = ['cpp', '-x', 'c', '-']
        # pipe = Popen(args, stdout=PIPE, stderr=PIPE, stdin=PIPE,
        #              universal_newlines=True)
        # code, err = pipe.communicate(code)
        return code

    def parse(self, code):
        '''
        Parses C code
        '''
        code = self.pre_process(code)
        # Meta data
        # Get AST
        parser = c_parser.CParser()
        try:
            self.ast = parser.parse(code)
        except plyparser.ParseError as e:
            raise ParseError(str(e))

        self.visit(self.ast)

    def visit_FileAST(self, node):
        '''
        FileAST - root node
        Attrs: ext (list)
        '''

        # Visit children
        fncs = set()
        for e in node.ext:
            self.visit(e)

    def visit_FuncDef(self, node):
        '''
        FuncDef - function definition
        Attrs: decl, param_decls, body
        '''

        self.fncdef = True
        (name, rtype, _) = self.visit(node.decl.type.type)

        params = []
        if node.decl.type.args:
            for param in node.decl.type.args.params:
                param = self.visit(param)
                if param == 'void':
                    continue
                if isinstance(param, Var):
                    param = (param.name, 'int')
                else:
                    param = param[:2]
                params.append(param)

        self.fncdef = False

        self.addfnc(name, params, rtype)
        for v, t in params:
            self.addtype(v, t)

        self.addloc(desc="at the beginning of the function '%s'" % (name,))
        self.visit(node.body)

        self.endfnc()

    def visit_FuncDecl(self, node):
        '''
        Function Declaration
        Attrs: args, type
        '''

        self.fncdef = True
        (name, rtype, _) = self.visit(node.type)
        params = []
        if node.args:
            for param in node.args.params:
                param = self.visit(param)
                if param == 'void':
                    continue
                if isinstance(param, Var):
                    param = (param.name, 'int')
                elif isinstance(param, str):
                    param = ('_', param)
                else:
                    param = param[:2]
                params.append(param)
        self.fncdef = False

        self.addfnc(name, params, rtype)

        for v, t in params:
            self.addtype(v, t)

        self.endfnc()

        return (name, rtype, None)

    def visit_Compound(self, node):
        '''
        Compound - composition of statements
        Attrs: block_items
        '''

        if node.block_items:
            for item in node.block_items:
                res = self.visit(item)

                if isinstance(res, Op) and res.name == 'FuncCall':
                    self.addexpr('_', res)

    def visit_Assignment(self, node):
        '''
        Assignment
        Attrs: op, lvalue, rvalue
        '''

        lvalue = self.visit_expr(node.lvalue)
        postincdec = self.postincdec
        self.postincdec = 0
        rvalue = self.visit(node.rvalue)
        postincdec, self.postincdec = self.postincdec, postincdec

        if not rvalue:
            rvalue = Const('?', line=node.coord.line)

        # Cases of assignment operator
        if node.op == '=':
            pass
        elif len(node.op) == 2 and node.op[1] == '=':
            rvalue = Op(node.op[0], lvalue.copy(), rvalue, line=rvalue.line)
        else:
            raise NotSupported("Assignment operator: '%s'" % (node.op,),
                               line=node.coord.line)

        # Distinguish lvalue (ID and Array)
        if isinstance(lvalue, Var):
            lval = lvalue

        elif (isinstance(lvalue, Op) and lvalue.name == '[]' and
              isinstance(lvalue.args[0], Var)):
            rvalue = Op('ArrayAssign', lvalue.args[0].copy(),
                        lvalue.args[1].copy(), rvalue, line=node.coord.line)
            lval = lvalue.args[0]

        else:
            raise NotSupported("Assignment lvalue '%s'" % (lvalue,),
                               line=node.coord.line)

        # List of expression
        if isinstance(rvalue, list):
            rvalue = rvalue[-1]

        # Special case when previous assignment was p++/p--
        # push this assignment before the previous one
        self.addexpr(lval.name, rvalue.copy(),
                     idx=-postincdec if postincdec else None)

        return lvalue

    def visit_EmptyStatement(self, node):
        '''
        Empty statement
        Attrs:
        '''

    def visit_ID(self, node):
        '''
        ID
        Attrs: name
        '''

        if node.name in self.CONSTS:
            return Const(node.name, line=node.coord.line)

        return Var(node.name, line=node.coord.line)

    def visit_InitList(self, node):
        '''
        Array Initialization List
        Attrs: exprs
        '''
        exprs = list(map(self.visit_expr, node.exprs or []))
        return Op('ArrayInit', *exprs, line=node.coord.line)

    def visit_BinaryOp(self, node):
        '''
        BinaryOp - binary operation
        Attrs: op, left, right
        '''

        return Op(node.op, self.visit_expr(node.left),
                  self.visit_expr(node.right), line=node.coord.line)

    def visit_UnaryOp(self, node):
        '''
        UnaryOp - unary operation
        Attrs: op, expr
        '''

        expr = self.visit_expr(node.expr)

        # Special cases
        # ++/--
        if node.op in ['++', '--']:
            if not isinstance(expr, Var):
                raise NotSupported('++/-- supported only for Vars',
                                   line=node.coord.line)
            self.addexpr(expr.name,
                         Op(node.op[1], expr.copy(), Const('1'),
                            line=node.coord.line))
            return expr

        elif node.op in ['p++', 'p--']:
            if not isinstance(expr, Var):
                raise NotSupported('p++/p-- supported only for Vars',
                                   line=node.coord.line)
            self.addexpr(expr.name,
                         Op(node.op[1], expr.copy(), Const('1'),
                            line=node.coord.line))
            self.postincdec += 1
            return expr

        return Op(node.op, expr, line=node.coord.line)

    def visit_ArrayRef(self, node):
        '''
        Array reference
        Attrs: name, subscript
        '''

        name = self.visit_expr(node.name)
        if not isinstance(name, Var):
            raise NotSupported("ArrayName: '%s'" % (name,))

        sub = self.visit_expr(node.subscript)

        return Op('[]', name, sub, line=node.coord.line)

    def visit_Constant(self, node):
        '''
        Constant
        Attrs: type, value
        '''

        return Const(node.value, line=node.coord.line)

    def visit_Cast(self, node):
        '''
        Expression case
        Attrs: to_type, expr
        '''
        tt = self.visit(node.to_type)
        expr = self.visit_expr(node.expr)
        return Op('cast', Const(tt), expr, line=node.coord.line)

    def visit_TernaryOp(self, node):
        '''
        Ternary Operator node
        Attrs: cond, iftrue, iffalse
        '''

        cond = self.visit_expr(node.cond)

        n = self.numexprs()
        ift = self.visit_expr(node.iftrue)
        iff = self.visit_expr(node.iffalse)

        if self.numexprs() > n:
            self.rmlastexprs(num=self.numexprs() - n)
            return self.visit_if(node, node.cond, node.iftrue, node.iffalse)

        return Op('ite', cond, ift, iff, line=node.coord.line)

    def visit_Switch(self, node):
        '''
        Switch statement
        Attrs: cond, stmt
        '''

        # Parse condition
        condexpr = self.visit_expr(node.cond)

        # Check that stmt is a compound of "case"/"defaults"
        # and covert to "if-then-else"
        # TODO: Check only one "case"/"default"
        if isinstance(node.stmt, c_ast.Compound):

            n = len(node.stmt.block_items)

            def convert(i):

                if i >= n:
                    return

                item = node.stmt.block_items[i]

                # Item statement
                stmt = (c_ast.Compound(item.stmts, coord=item.coord)
                        if isinstance(item.stmts, list) else item.stmts)

                if i == (n - 1) and isinstance(item, c_ast.Default):
                    return stmt

                if isinstance(item, c_ast.Case):
                    next = convert(i + 1)

                    ifcond = c_ast.BinaryOp('==', node.cond, item.expr,
                                            coord=item.expr.coord)
                    return c_ast.If(ifcond, stmt, next, coord=item.expr.coord)

            stmt = convert(0)
            if stmt:
                insw = self.inswitch
                self.inswitch = True

                res = self.visit(stmt)

                self.inswitch = insw

                return res

        # Otherwise not-supported
        raise NotSupported("Switch statement", line=node.coord.line)

    def visit_FuncCall(self, node):
        '''
        FuncCall
        Attrs: name, args
        '''

        # Get (and check) name
        function_reference = self.visit_expr(node.name)
        if not isinstance(function_reference, Var):
            raise NotSupported("Non-var function name: '%s'" % (function_reference,),
                               line=function_reference.line)

        # Parse args
        args = self.visit(node.args) or []

        # Special cases (scanf & printf)
        if function_reference.name == 'scanf':
            return self.visit_scanf(node, args)

        elif function_reference.name == 'printf':
            return self.visit_printf(node, args)

        # Program functions
        elif function_reference.name in self.fncs:
            return Op('FuncCall', function_reference, *args, line=node.coord.line)

        # Library functions
        elif function_reference.name in self.LIB_FNCS:
            return Op(function_reference.name, *args, line=node.coord.line)

        else:
            raise NotSupported(
                "Unsupported function call: '%s'" % (function_reference.name,),
                line=node.coord.line)

    def visit_printf(self, node, args):
        '''
        printf function call
        '''

        # Extract format and args
        if len(args) == 0:
            self.addwarn("'printf' with zero args at line %s" % (
                node.coord.line,))
            fmt = Const('?', line=node.coord.line)
        else:
            if isinstance(args[0], Const):
                fmt = args[0]
                args = args[1:]
            else:
                self.addwarn("First argument of 'printf' at lines %s should \
be a format" % (node.coord.line,))
                fmt = Const('?', line=node.coord.line)

        fmt.value = fmt.value.replace('%lf', '%f')
        fmt.value = fmt.value.replace('%ld', '%d')
        fmt.value = fmt.value.replace('%lld', '%d')

        expr = Op('StrAppend', Var(VAR_OUT),
                  Op('StrFormat', fmt, *args, line=node.coord.line),
                  line=node.coord.line)
        self.addexpr(VAR_OUT, expr)

    def visit_scanf(self, node, args):
        # Check format
        if len(args) == 0:
            self.warn("'scanf' without arguments at line %s (ignored)", node.coord.line)
        else:
            format_string = args[0]
            if isinstance(format_string, Const) and format_string.value[0] == '"' and format_string.value[-1] == '"':
                format_string = format_string.value[1:-1]
                args = args[1:]
            else:
                self.warn("First argument of 'scanf' at line %s should be a \ (string) format (ignored)",
                          node.coord.line)
                format_string = ''
                args = []
        # Extract format arguments
        conversion_specifiers = list(re.findall(r'(%((d)|(i)|(li)|(lli)|(ld)|(lld)|(lf)|(f)|(s)|(c)))', format_string))

        # Check argument number
        if len(conversion_specifiers) != len(args):
            self.addwarn("Mismatch between format and number of argument(s)\ of 'scanf' at line %s.",
                         node.coord.line)

            if len(args) > len(conversion_specifiers):
                conversion_specifiers += ['*' for _ in range(len(args) - len(conversion_specifiers))]

        # Iterate formats and arguments
        vars_list = []
        for conversion_specifier, arg in zip(conversion_specifiers, args):
            if conversion_specifier:
                conversion_specifier = conversion_specifier[0]
            if conversion_specifier in ['%d', '%ld', '%i', '%li', '%lli', '%lld']:
                argument_type = 'int'
            elif conversion_specifier in ['%c']:
                argument_type = 'char'
            elif conversion_specifier in ['%s']:
                argument_type = 'string'
            elif conversion_specifier in ['%f', '%lf']:
                argument_type = 'float'
            elif conversion_specifier == '*':
                argument_type = '*'
            else:
                self.addwarn("Invalid 'scanf' format at line %s.", node.coord.line)
                argument_type = '*'

            # Check if argument is: &x
            if isinstance(arg, Op) and arg.name == '&' and len(arg.args) == 1:
                arg = arg.args[0]
            elif isinstance(arg, Var) or (isinstance(arg, Op) and arg.name == '[]'):
                self.addwarn("Forgoten '&' in 'scanf' at line %s?", node.coord.line)
            else:
                raise NotSupported("Argument to scanf: '%s'" % (arg,), line=node.coord.line)

            # Add operations
            rexpr = Op('ListHead', Const(argument_type), Var(VAR_IN), line=node.coord.line)
            if isinstance(arg, Var):
                self.addexpr(arg.name, rexpr)
            elif isinstance(arg, Op) and arg.name == '[]' and isinstance(arg.args[0], Var):
                self.addexpr(arg.args[0].name, Op('ArrayAssign', arg.args[0], arg.args[1], rexpr, line=node.coord.line))
            else:
                raise NotSupported("Argument to scanf: '%s'" % (arg,), line=node.coord.line)
            self.addexpr(VAR_IN, Op('ListTail', Var(VAR_IN), line=node.coord.line))
            vars_list.append(arg)

        return Op("scanf", *vars_list, line=node.coord.line)

    def visit_ExprList(self, node):
        '''
        ExprList
        Attrs: exprs
        '''

        return list(map(self.visit_expr, node.exprs))

    def visit_If(self, node):
        '''
        If node
        Attrs: cond, iftrue, iffalse
        '''

        self.visit_if(node, node.cond, node.iftrue, node.iffalse)

    def visit_While(self, node):
        '''
        While
        Attrs: cond, stmt
        '''

        if self.inswitch:
            raise NotSupported("Loop inside switch", line=node.coord.line)

        self.visit_loop(node, None, node.cond, node.cond, node.stmt,
                        False, 'while')

    def visit_DoWhile(self, node):
        '''
        DoWhile loop
        Attrs: cond, stmt
        '''

        if self.inswitch:
            raise NotSupported("Loop inside switch", line=node.coord.line)

        self.visit_loop(node, None, node.cond, None, node.stmt,
                        True, 'do-while')

    def visit_For(self, node):
        '''
        For
        Attrs: init, cond, next, stmt
        '''

        if self.inswitch:
            raise NotSupported("Loop inside switch", line=node.coord.line)

        self.visit_loop(node, node.init, node.cond, node.next, node.stmt,
                        False, 'for')

    def visit_Return(self, node):
        '''
        Return node
        Attrs: expr
        '''

        expr = self.visit_expr(node.expr)
        if not expr:
            expr = Const('top', line=node.coord.line)
        self.addexpr(VAR_RET, expr)

    def visit_Break(self, node):
        '''
        Break node
        Attrs:
        '''
        if self.inswitch or self.nobcs:
            return

        # Find loop
        lastloop = self.lastloop()
        if not lastloop:
            self.addwarn("'break' outside loop at line %s", node.coord.line)
            return

        # Add new location and jump to exit location
        self.hasbcs = True
        preloc = self.loc
        self.loc = self.addloc(
            desc="after 'break' statement at line %s" % (
                node.coord.line,))
        self.addtrans(preloc, True, lastloop[1])

    def visit_Continue(self, node):
        '''
        Continue node
        Attrs:
        '''

        if self.nobcs:
            return

        # Find loop
        lastloop = self.lastloop()
        if not lastloop:
            self.addwarn("'continue' outside loop at line %s", node.coord.line)
            return

        # Add new location and jump to condition location
        self.hasbcs = True
        preloc = self.loc
        self.loc = self.addloc(
            desc="after 'continue' statement at line %s" % (
                node.coord.line,))
        self.addtrans(preloc, True, lastloop[2] if lastloop[2] else lastloop[0])

    def visit_Label(self, node):
        '''
        Label
        Attrs: name, stmt
        '''
        self.addwarn('Ignoring label at line %s.', node.coord.line)
        return self.visit(node.stmt)

    def visit_Goto(self, node):
        '''
        Goto
        Attrs: name
        '''
        raise NotSupported('Not supporting GOTO - it is considered harmful.')

    def visit_Decl(self, node):
        '''
        Decl - Declaration
        Attrs: name, quals, storage, funcspec, type, init, bitsize
        (using only: name, type & init)
        '''

        (name, type, dim) = self.visit(node.type)
        init = self.visit_expr(node.init, allownone=True)

        if not self.fncdef:
            try:
                self.addtype(name, type)
            except AssertionError:
                self.addwarn("Ignored global definition '%s' on line %s." % (
                    name, node.coord.line,))
                return

        if init and dim:
            raise NotSupported("Array Init & Create together",
                               line=node.coord.line)

        if init:
            self.addexpr(name, init)

        if dim and not self.fncdef:
            self.addexpr(name, Op('ArrayCreate', dim, line=dim.line))

        return (name, type, dim)

    def visit_ArrayDecl(self, node):
        '''
        ArrayDecl - Array declaration
        Attrs: type, dim, dim_quals (ignored)
        '''

        (name, type, dim) = self.visit(node.type)

        if dim is not None or type.endswith('[]'):
            raise NotSupported('Double Array', line=node.coord.line)

        type += '[]'
        return (name, type, self.visit_expr(node.dim))

    def visit_DeclList(self, node):
        '''
        DeclList
        Attrs: decls
        '''

        for decl in node.decls:
            self.visit(decl)

    def visit_TypeDecl(self, node):
        '''
        TypeDecl - Type declaration
        Attrs: declname, quals, type
        (quals is ignored)
        '''

        return (node.declname, self.visit(node.type), None)

    def visit_IdentifierType(self, node):
        '''
        IdentifierType - Type name
        Attrs: names
        '''

        name = '_'.join(node.names)
        return self.TYPE_SYNONYMS.get(name, name)

    def visit_Typename(self, node):
        '''
        Type name
        Attrs: quals, type
        '''
        (_, name, _) = self.visit(node.type)
        return str(name)

    def getline(self, node):
        return node.coord.line


addlangparser('c', CParser)
