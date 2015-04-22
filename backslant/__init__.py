import sys
import ast
from io import StringIO

from markupsafe import Markup, escape
from funcparserlib.parser import NoParseError

from .lexer import idented_tokenizer
from .parser import bs_parser


class AstParsers:
    def string(text, childs=None, line_n_offset={}, parse_ast=None, filename='<backslant>'):
        yield ast.Expr(
            value=ast.Yield(
                value=ast.Str(s=text.strip(text[0])),
            ),
            **line_n_offset
        )

    def tag(args, childs=None, line_n_offset={}, parse_ast=None, filename='<backslant>'):
        name, classes_n_id, arguments, text = args
        single_attrs = []
        pair_keys = []
        pair_vals = []
        classes = []
        ids = []
        kwargs = None
        keywords = []
        for typ, cls_or_id in classes_n_id:
            if typ == 'class':
                classes.append(cls_or_id)
            elif typ == 'id':
                ids.append(cls_or_id)
        if classes:
            pair_keys.append('class')
            pair_vals.append(ast.Str(s=' '.join(classes)))
        # TODO do we need multidict?
        if ids:
            pair_keys.append('id')
            pair_vals.append(ast.Str(s=ids[-1]))
        if isinstance(arguments, str):
            kwargs = ast.parse(arguments, filename=filename).body[0].value
        else:
            for arg in (arguments or []):
                if isinstance(arg, str):
                    single_attrs.append(ast.Str(s=arg))
                else:
                    pair_keys.append(arg[0])
                    pair_vals.append(ast.parse(arg[1], filename=filename).body[0].value)
        # _tag_start(name, *single_attrs, **attributes)
        if pair_keys and pair_vals:
            for key, value in zip(pair_keys, pair_vals):
                keywords.append(ast.keyword(arg=key, value=value))
        yield ast.Expr(
            value=ast.Yield(
                value=ast.Call(func=ast.Name(id='_tag_start', ctx=ast.Load()),
                    args=[ast.Str(s=name)] + single_attrs,
                    keywords=keywords,
                    starargs=None,
                    kwargs=kwargs
                ),
            ),
            **line_n_offset
        )
        if text:
            yield from AstParsers.string(text)
        if childs:
            yield from childs
        yield ast.Expr(
            value=ast.Yield(
                value=ast.Call(func=ast.Name(id='_tag_stop', ctx=ast.Load()),
                    args=[ast.Str(name)] + single_attrs,
                    keywords=keywords,
                    starargs=None,
                    kwargs=None
                ),
            ),
            **line_n_offset
        )

    def _flat_addons(addons):
        for addon in addons:
            if isinstance(addon, list):
                for subaddon in addon:
                    if subaddon:
                        yield subaddon
            elif addon:
                yield addon

    def python(string, addons, childs=None, line_n_offset={}, parse_ast=None, filename='<backslant>'):
        if string == 'try:':
            res = ast.Try(
                body=list(childs),
                handlers=[],
                orelse=[],
                finalbody=[],
                **line_n_offset
            )
        else:
            if string.endswith(':'):
                string = string + ' pass'
            res = ast.parse(string, filename=filename).body[0]
            res.lineno = line_n_offset['lineno']
            res.col_offset = line_n_offset['col_offset']
            if childs and getattr(res, 'body', None) and isinstance(res.body[0], ast.Pass):
                res.body = list(childs)
        elsenode = res
        for addon in AstParsers._flat_addons(addons):
            # print('addon', addon, addons)
            (typ, (ln, off), s), block = addon
            childs = list(parse_ast(block))
            if s == 'else:':
                elsenode.orelse = childs
            elif s.startswith('elif'):
                parsed = ast.parse(s[2:] + 'pass', filename=filename).body[0]
                parsed.body = childs
                parsed.lineno = ln
                parsed.col_offset = off
                elsenode.orelse = [parsed]
                elsenode = parsed
            elif s == 'finally:':
                elsenode.finalbody = [childs]
            elif s.startswith('except'):
                except_hndl = ast.parse('try: pass\n' + s + 'pass', filename=filename).body[0].handlers[0]
                except_hndl.body = childs
                except_hndl.lineno = ln
                except_hndl.col_offset = off
                elsenode.handlers = (elsenode.handlers or []) + [except_hndl]
        ast.fix_missing_locations(res)
        yield res

    def macro(name, *arg, childs=None, line_n_offset={}, parse_ast=None, filename='<backslant>'):
        if name == 'call':
            if not arg:
                raise ValueError('{} :call need function call as argument'.format(lineno))
            arg = arg[0]
            node = ast.parse(arg.strip())
            call = node.body[0].value
            for child in childs:
                if not isinstance(child, ast.FunctionDef):
                    raise ValueError('{} only function defs are allowed under :call directive'.format(lineno))
                yield child
                name = child.name
                call.keywords.append(
                    ast.keyword(arg=name, value=ast.Name(id=name, ctx=ast.Load()))
                )
            yield ast.Expr(value=ast.YieldFrom(value=call))
        else:
            yield ast.FunctionDef(
                name=name,
                args=ast.arguments(
                    args=[],
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[],
                ),
                body=list(childs),
                decorator_list=[],
                returns=None,
            )


def parse_to_ast(filename):
    def parse_ast(ast, space=0):
        if not ast:
            return
        for ast_node in ast:
            # print('ast_node', ast_node)
            line, block = ast_node
            if not line:
                continue
            # print(' ' * space, line)
            converter_name, (lineno, offset), *args = line
            line_n_offset = {'lineno': lineno, 'col_offset': offset}
            converter = getattr(AstParsers, converter_name, None)
            if converter:
                yield from converter(
                    *args,
                    childs=parse_ast(block, space=space + 1),
                    line_n_offset=line_n_offset,
                    parse_ast=parse_ast,
                    filename=filename
                )
    # for tok in idented_tokenizer(open(filename).read()):
    #     print(tok)
    try:
        ast = bs_parser.parse(list(idented_tokenizer(open(filename).read())))
    except NoParseError as e:
        print(e.__dict__)
        raise
    return list(parse_ast(ast))


def func_compile(filename):
    body = parse_to_ast(filename)
    is_plain = any(isinstance(expr, ast.Expr) and isinstance(expr.value, (ast.Yield, ast.YieldFrom)) for expr in body)
    if is_plain:
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
                body=body,
                decorator_list=[],
                returns=None,
            )],
            lineno=1, col_offset=0,
        )
    else:
        result_ast = ast.Module(
            body=body,
            lineno=1, col_offset=0,
        )
    result_ast = ast.fix_missing_locations(result_ast)
    # dump_ast(result_ast)
    return compile(result_ast, filename, 'exec')


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


def tag_attribute(name, value):
    return u'%s="%s"' % (escape(name), escape(value))


def start_tag(_tag_name, *single_args, ** kwargs):
    attributes =' '.join(
        [tag_attribute(name, value) for name, value in kwargs.items()]
        + [escape(name) for name in single_args]
    )
    if attributes:
        return Markup('<{name} {attributes}>'.format(name=_tag_name.rstrip('/'), attributes=attributes))
    return Markup('<{}>'.format(_tag_name.rstrip('/')))


def stop_tag(_tag_name, *single_attrs, **kwargs):
    if _tag_name[-1] == '/':
        return ''
    return Markup('</{}>'.format(_tag_name))


import imp
from importlib.machinery import ModuleSpec
import os.path as op
class PymlFinder(object):
    def __init__(self, basepath, hook='backslant_hook'):
        self.basepath = basepath
        self.hook = hook
        # print('FINDER', basepath)

    def find_spec(self, fullname, path, target_module):
        # print(fullname, path, target_module)
        if not fullname.startswith(self.hook):
            return
        if fullname == self.hook:
            return ModuleSpec(fullname, TopLevelLoader(fullname, self.basepath), origin=path, is_package=True)
        segments = fullname[len(self.hook) + 1:].split('.')
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
        mod.__file__ = self.path
        mod.__path__ = []
        return mod


class PymlLoader(object):
    def __init__(self, filename):
        self.filename = filename

    def load_module(self, fullname):
        # print(self.filename, fullname)
        mod = sys.modules.setdefault(fullname, imp.new_module(fullname))
        mod.__loader__ = self
        mod.__package__ = '.'.join(fullname.split('.')[:-1])
        mod.__file__ = self.filename
        mod.__dict__['_tag_start'] = start_tag
        mod.__dict__['_tag_stop'] = stop_tag
        code = func_compile(self.filename)
        exec(code, mod.__dict__)
        return mod


if __name__ == '__main__':
    sys.meta_path.insert(0, PymlFinder('example'))
    import backslant_hook.templates.test as test
    index = 0
    for chunk in test.render(title='The Incredible'):
        if chunk.startswith('</'):
            index = index - 1
        print('    ' * index, chunk)
        if chunk.startswith('<') and not chunk.startswith('</'):
            index = index + 1
