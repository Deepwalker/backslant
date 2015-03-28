import sys
import ast


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


class Tag:
    def __init__(self, name):
        self.name = name

    def start(self):
        return '<{}>'.format(self.name)

    def stop(self):
        return '</{}>'.format(self.name)


def convert_to_ast(idented_tree, order=0):
    elements = []
    for lineno, node_string, childs in idented_tree:
        ast_childs = convert_to_ast(childs, order=order)
        if node_string.startswith('-'):
            if node_string.endswith(':'):
                node_string = node_string + ' pass'
            res = ast.parse(node_string[1:].strip(), filename='text.pyml').body[0]
            res.lineno = lineno
            res.col_offset = 0
            if childs and isinstance(res.body[0], ast.Pass):
                res.body = ast_childs or []
            elements.append(res)
            continue
        node, *args = node_string.split(' ', 1)
        line_n_offset = {'lineno': lineno + 1, 'col_offset': 0}
        node_name = 'name_%s_%s' % (lineno, order)
        elements.append(ast.Assign(
            targets=[ast.Name(id=node_name, ctx=ast.Store())],
            value=ast.Call(
                func=ast.Name(id='Tag', ctx=ast.Load()),
                args=[ast.Str(node, **line_n_offset)],
                keywords=[],
                starargs=None,
                kwargs=None,
            ),
            **line_n_offset
        ))
        elements.append(ast.Expr(
            value=ast.Yield(
                value=ast.Call(func=ast.Attribute(
                        value=ast.Name(id=node_name, ctx=ast.Load()),
                        attr='start', ctx=ast.Load(),
                    ),
                    args=[], keywords=[], starargs=None, kwargs=None,
                ),
            ),
            **line_n_offset
        ))
        elements.extend(ast_childs)
        elements.append(ast.Expr(
            value=ast.Yield(
                value=ast.Call(func=ast.Attribute(
                    value=ast.Name(id=node_name, ctx=ast.Load()),
                    attr='stop', ctx=ast.Load()), args=[], keywords=[], starargs=None, kwargs=None,
                ),
            ),
            **line_n_offset
        ))
    return elements


def convert_internal_ast_to_python_code(idented_tree):
    result_ast = ast.Module(
        body=[ast.FunctionDef(
            name='render',
            args=ast.arguments(
                args=[],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=convert_to_ast(idented_tree),
            decorator_list=[],
            returns=None,
        )],
        lineno=1, col_offset=0,
    )
    result_ast = ast.fix_missing_locations(result_ast)
    return compile(result_ast, 'test.pyml', 'exec')


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
    def __init__(self, filename):
        self.filename = filename

    def load_module(self, fullname):
        print(self.filename, fullname)
        mod = sys.modules.setdefault(fullname, imp.new_module(fullname))
        mod.__loader__ = self
        mod.__package__ = '.'.join(fullname.split('.')[:-1])
        mod.__dict__['Tag'] = Tag
        code = convert_internal_ast_to_python_code(parse_file(self.filename))
        exec(code, mod.__dict__)
        return mod


if __name__ == '__main__':
    sys.meta_path.insert(0, PymlFinder('.'))
    import backslant_hook.templates.test as test
    print(list(test.render()))
