import sys
import ast
import pyparsing as pp
from markupsafe import Markup, escape


def find_indent(lst):
    """ given a list of text strings, returns a list containing the
    indentation levels for each string
    """
    space_counts = [len(s) - len(s.lstrip(' ')) for s in lst]
    indents = sorted(set(space_counts))
    level_ref = {indents[i]: i for i in range(len(indents))}
    return [level_ref[i] + 1 for i in space_counts]


def parse_file(filename):
    """ Return non python AST
    """
    lines = [line.rstrip() for line in open(filename).readlines()]
    idented_tree = []
    parent_nodes = []
    current_node = idented_tree
    current_ident = 1

    for line_no, (ident, line) in enumerate(zip(find_indent(lines), lines)):
        # print(line_no, ident, line)
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if ident == current_ident:
            current_node.append((line_no, stripped, []))
            continue
        if ident > current_ident:
            if ident - current_ident > 1:
                raise Exception('wrong identation')
            parent_nodes.append(current_node)
            current_node = current_node[-1][2]
            current_ident = ident
            current_node.append((line_no, stripped, []))
        if ident < current_ident:
            parent_nodes = parent_nodes[:ident]
            prev_node = parent_nodes.pop()
            prev_node.append((line_no, stripped, []))
            current_ident = ident
            current_node = prev_node
    return idented_tree


def create_parser():
    html_chars = pp.alphanums + '-_'
    tag_def = pp.Combine(pp.Optional(pp.Literal('!')) + pp.Word(html_chars) + pp.Optional(pp.Literal('/')))
    tag_class = pp.Combine(pp.Literal('.') + pp.Word(html_chars))
    tag_id = pp.Combine(pp.Literal('#') + pp.Word(html_chars))
    attribute_name = pp.Word(html_chars)

    def parse_attribute_value(s, l, t):
        return ast.parse(s[t._original_start:t._original_end]).body[0].value
    attribute_value = pp.originalTextFor(
          pp.sglQuotedString()
        ^ pp.dblQuotedString()
        ^ pp.nestedExpr()
        ^ pp.nestedExpr('[', ']')
    ).setParseAction(parse_attribute_value)

    def parse_tag_attribute(s, l, t):
        return t
    tag_attribute = pp.Group(attribute_name + pp.Suppress('=') + attribute_value).setParseAction(parse_tag_attribute)
    tag_dict = pp.nestedExpr('{', '}').setParseAction(
        lambda s, l, t: [[ast.parse(s[l:]).body[0].value]]
    )
    single_attr = pp.Word(html_chars).setParseAction(lambda s, l, t: ast.Str(s=t[0]))
    tag_grammar = (
        tag_def
        + pp.Group(pp.ZeroOrMore(tag_class ^ tag_id))
        + (tag_dict ^ pp.Group(pp.ZeroOrMore(tag_attribute ^ single_attr)))
    )
    def parse_tag(node_string):
        node, attrs_keys, node_attrs = tag_grammar.parseString(node_string)
        node_attrs_keys = []
        node_attrs_values = []
        single_attrs = []
        for node_attr in node_attrs:
            if isinstance(node_attr, ast.Dict):
                return node, None, node_attr
            if isinstance(node_attr, ast.Str):
                single_attrs.append(node_attr)
            elif isinstance(node_attr, pp.ParseResults):
                node_attrs_keys.append(ast.Str(s=str(node_attr[0])))
                node_attrs_values.append(node_attr[1])
        if node_attrs_keys:
            node_attrs = ast.Dict(
                keys=node_attrs_keys,
                values=node_attrs_values
            )
        else:
            node_attrs = None
        # print('RET', node, single_attrs, node_attrs)
        return node, single_attrs, node_attrs
    return parse_tag

parse_tag = create_parser()


def dump_ast(node, tabs=0):
    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.stack = 0
        def visit(self, node):
            space = "    " * self.stack
            print(space + repr(node))
            if hasattr(node, '_fields'):
                for field in node._fields:
                    if not isinstance(getattr(node, field), ast.AST):
                        print(space, field, '=', repr(getattr(node, field)))
            self.stack += 1
            super(Visitor, self).visit(node)
            self.stack -= 1
    Visitor().visit(node)


def _to_string(items):
    def inner(items):
        for line_no, node, childs in items:
            yield node
            yield from inner(childs)
    return ''.join(inner(items))


def _convert_to_ast(idented_tree, order=0):
    node_with_else = None # track if and for
    for lineno, node_string, childs in idented_tree:
        if node_string == ':noescape':
            s = _to_string(childs)
            yield ast.Expr(
                value=ast.Yield(
                    value=ast.Str(s=s)
                )
            )
            continue
        ast_childs = _convert_to_ast(childs, order=order)
        elif_ = False
        if node_string.startswith('-'):
            node_string = node_string[1:].strip()
            if node_string == 'else':
                node_with_else.orelse = list(ast_childs) or []
            else:
                if node_string.startswith('elif '):
                    node_string = node_string[2:]
                    elif_ = True
                else:
                    # swap out (if|for)node
                    node_with_else = None
                if node_string.endswith(':'):
                    node_string = node_string + ' pass'
                res = ast.parse(node_string, filename='text.pyml').body[0]
                res.lineno = lineno + 1
                res.col_offset = 0
                if not elif_ and isinstance(res, (ast.If, ast.For)):
                    node_with_else = res
                if childs and isinstance(res.body[0], ast.Pass):
                    res.body = list(ast_childs) or []
                ast.fix_missing_locations(res)
                if elif_:
                    node_with_else.orelse = [res]
                    node_with_else = res
                else:
                    yield res
            continue
        if node_string.startswith('"'):
            yield ast.Expr(
                value=ast.Yield(
                    value=ast.Str(s=node_string[1:])
                )
            )
            continue
        node, single_attrs, node_attrs = parse_tag(node_string)
        line_n_offset = {'lineno': lineno + 1, 'col_offset': 0}
        node_name = '%s_%s_%s' % (node, lineno, order)
        yield ast.Assign(
            targets=[ast.Name(id=node_name, ctx=ast.Store())],
            value=ast.Call(
                func=ast.Name(id='Tag', ctx=ast.Load()),
                args=[ast.Str(node, **line_n_offset)] + (single_attrs or []),
                keywords=[],
                starargs=None,
                kwargs=node_attrs,
            ),
            **line_n_offset
        )
        yield ast.Expr(
            value=ast.Yield(
                value=ast.Call(func=ast.Attribute(
                        value=ast.Name(id=node_name, ctx=ast.Load()),
                        attr='start', ctx=ast.Load(),
                    ),
                    args=[], keywords=[], starargs=None, kwargs=None,
                ),
            ),
            **line_n_offset
        )
        yield from ast_childs
        yield ast.Expr(
            value=ast.Yield(
                value=ast.Call(func=ast.Attribute(
                    value=ast.Name(id=node_name, ctx=ast.Load()),
                    attr='stop', ctx=ast.Load()), args=[], keywords=[], starargs=None, kwargs=None,
                ),
            ),
            **line_n_offset
        )

def convert_to_ast(idented_tree, order=0):
    return list(_convert_to_ast(idented_tree, order))



def convert_internal_ast_to_python_code(idented_tree, filename='<unknown>'):
    result_ast = ast.Module(
        body=[ast.FunctionDef(
            name='render',
            args=ast.arguments(
                args=[],
                vararg=ast.arg(arg='arguments', annotation=None),
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=ast.arg(arg='options', annotation=None),
                defaults=[],
            ),
            body=convert_to_ast(idented_tree),
            decorator_list=[],
            returns=None,
        )],
        lineno=1, col_offset=0,
    )
    result_ast = ast.fix_missing_locations(result_ast)
    # dump_ast(result_ast)
    return compile(result_ast, filename, 'exec')


NoValue = object()
def tag_attribute(name, value):
    if value is NoValue:
        return escape(name)
    return u'%s="%s"' % (escape(name), escape(value))


class Tag:
    def __init__(self, name, *single_args, **kwargs):
        self.has_stop = not name.endswith('/')
        self.name = name.rstrip('/')
        self.kwargs = kwargs
        self.single_args = single_args

    def start(self):
        attributes =' '.join(
            [tag_attribute(name, value) for name, value in self.kwargs.items()]
            + [escape(name) for name in self.single_args]
        )
        if attributes:
            return Markup('<{name} {attributes}>'.format(name=self.name, attributes=attributes))
        return Markup('<{}>'.format(self.name))

    def stop(self):
        if self.has_stop:
            return Markup('</{}>'.format(self.name))


def convert_to_function(code):
    context = {'Tag': Tag}
    exec(code, context)
    return context['render']


import imp
from importlib.machinery import ModuleSpec
import os.path as op
class PymlFinder(object):
    def __init__(self, basepath, hook='backslant_hook'):
        self.basepath = basepath
        self.hook = hook
        # print('LOADER', basepath)

    def find_spec(self, fullname, path, target_module):
        # print(fullname, path, target_module)
        if not fullname.startswith(self.hook):
            return
        if fullname == self.hook:
            return ModuleSpec(fullname, TopLevelLoader(fullname, path), origin=path, is_package=True)
        segments = fullname.split('.')[1:] # strip hook
        path = op.join(self.basepath, *segments)
        if op.isdir(path):
            is_package = True
            return ModuleSpec(fullname, TopLevelLoader(fullname, path), origin=path, is_package=True)
        path = path + '.bs'
        if not op.exists(path):
            return None
        spec = ModuleSpec(fullname, PymlLoader(path), origin=path, is_package=False)
        return spec


class TopLevelLoader(object):
    def __init__(self, fullname, path):
        self.fullname = fullname
        self.path = path

    def create_module(self):
        return None

    def load_module(self, fullname):
        mod = sys.modules.setdefault(fullname, imp.new_module(fullname))
        mod.__loader__ = self
        mod.__package__ = fullname
        mod.__path__ = []
        return mod


class PymlLoader(object):
    def __init__(self, filename, tag_class=Tag):
        self.filename = filename
        self.tag_class = tag_class

    def load_module(self, fullname):
        # print(self.filename, fullname)
        mod = sys.modules.setdefault(fullname, imp.new_module(fullname))
        mod.__loader__ = self
        mod.__package__ = '.'.join(fullname.split('.')[:-1])
        mod.__dict__['Tag'] = self.tag_class
        code = convert_internal_ast_to_python_code(parse_file(self.filename), filename=self.filename)
        exec(code, mod.__dict__)
        return mod


if __name__ == '__main__':
    sys.meta_path.insert(0, PymlFinder('example'))
    import backslant_hook.templates.test as test
    index = 0
    for chunk in test.render(title='The Incredible'):
        if chunk == None:
            continue
        if chunk.startswith('</'):
            index = index - 1
        print('    ' * index, chunk)
        if chunk.startswith('<') and not chunk.startswith('</'):
            index = index + 1
