import sys
import ast
import token
from io import StringIO
from tokenize import generate_tokens

import pyparsing as pp
from markupsafe import Markup, escape
from funcparserlib.parser import many, maybe, skip, some, forward_decl, NoParseError


class Token(object):
    def __init__(self, code, value, start=(0, 0), stop=(0, 0), line=''):
        self.code = code
        self.value = value
        self.start = start
        self.stop = stop
        self.line = line
        self.type = token.tok_name[self.code]

    def __unicode__(self):
        pos = '-'.join('%d,%d' % x for x in [self.start, self.stop])
        return "%s %s '%s'" % (pos, self.type, self.value)

    def __repr__(self):
        return 'Token(%r, %r, %r, %r, %r)' % (
            self.type, self.value, self.start, self.stop, self.line)

    def __eq__(self, other):
        return (self.code, self.value) == (other.code, other.value)


def tokenize(io):
    'str -> [Token]'
    # print list(unicode(Token(*t))
    #     for t in generate_tokens(StringIO(s).readline)
    #     if t[0] not in [NL, token.NEWLINE])
    return [Token(*t) for t in generate_tokens(io)]


def func_parser():
    def recursive_join(toks):
        def inner(tks):
            if tks is None:
                return
            if isinstance(tks, str):
                yield tks
                return
            if isinstance(tks, Token):
                yield tks.value
                return
            for tok in tks:
                if isinstance(tok, Token):
                    yield tok.value
                else:
                    yield from inner(tok)
        return ''.join(inner(toks))

    def prn(tks):
        print(repr(tks))
        return tks

    def combine(tks):
        def get_tok(toks, index=0):
            if isinstance(toks, Token):
                return toks
            elif isinstance(toks, (tuple, list)):
                toks = [t for t in toks if t]
                return get_tok(toks[index])
        if not tks:
            return ''
        first = get_tok(tks)
        last = get_tok(tks, index=-1)
        return first.line[first.start[1]:last.stop[1]]

    sometok = lambda s: some(lambda tok: tok.value == s)
    sometype = lambda t: some(lambda tok: tok.type == t)
    no_dent = some(lambda tok: tok.type not in ['INDENT', 'DEDENT', 'NEWLINE'])
    nodent = lambda tok: tok.type not in ['INDENT', 'DEDENT', 'NEWLINE']
    newline = skip(sometok('\n'))
    name = sometype('NAME')
    python_name = name + many(sometok('.') + name)
    to_end_of_line = many(no_dent) >> combine
    take_value = lambda tok: tok.value

    def paren_match(start, end=None):
        if not end:
            end = start
        parens = forward_decl()
        no_paren_dent_nl = some(lambda tok: nodent(tok) and not tok.value in (start, end))
        parens.define(sometok(start) + many(no_paren_dent_nl | parens) + sometok(end))
        return parens

    python_call = (sometok('-') + to_end_of_line) >> (lambda toks: ('python', toks[0].start, toks[1]))
    macro = (sometok(':') + sometype('NAME') + to_end_of_line) >> (lambda toks: ('macro', toks[0].start, toks[1].value, toks[2]))
    string = (sometok('|') + many(no_dent)) >> (lambda toks: ('string', toks[0].start, toks[0].line.strip()))
    string = string | (sometype('STRING') >> (lambda tok: ('string', tok.start, tok.value)))
    text = sometype('STRING') >> take_value
    # HTML attr
    html_name = (name + many(sometok('-') + name))
    html_name_str = html_name >> combine
    attribute_value = (sometype('STRING') >> take_value) | ((paren_match('(', ')') | python_name) >> combine)
    single_attr = html_name_str
    pair_attr = (html_name_str + sometok('=') + attribute_value) >> (lambda toks: (toks[0], toks[2]))
    attribute = pair_attr | single_attr
    attributes = (
        ((sometok('(') + many(attribute) + sometok(')')) >> (lambda toks: toks[1]))
        | (paren_match('{', '}') >> combine)
    )
    tag_class = (sometok('.') + html_name_str) >> (lambda toks: ('class', toks[1]))
    tag_id = sometype('COMMENT') >> (lambda tok: ('id', tok.value))
    tag_name = (maybe(sometok('!')) + html_name + maybe(sometok('/'))) >> combine
    tag = tag_name + many(tag_class | tag_id) + maybe(attributes) + maybe(text) >> (lambda toks: ('tag', (0, 0), toks))

    definition = (tag | python_call | macro | string)
    line = forward_decl()
    block = (skip(sometype('INDENT')) + many(line) + skip(sometype('DEDENT')))
    line.define(maybe(definition) + newline + maybe(block))
    parser = (many(line) + skip(sometype('ENDMARKER')))

    return parser


class AstParsers:
    def string(text, childs=None, line_n_offset={}):
        yield ast.Expr(
            value=ast.Yield(
                value=ast.Str(s=text),
            ),
            **line_n_offset
        )

    def tag(args, childs=None, line_n_offset={}):
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
            kwargs = ast.parse(arguments, filename='<filename>').body[0].value
        else:
            for arg in (arguments or []):
                if isinstance(arg, str):
                    single_attrs.append(ast.Str(s=arg))
                else:
                    pair_keys.append(arg[0])
                    pair_vals.append(ast.parse(arg[1], filename='<filename>').body[0].value)
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

    def python(string, childs=None, line_n_offset={}):
        if string.endswith(':'):
            string = string + ' pass'
        res = ast.parse(string, filename='text.pyml').body[0]
        res.lineno = line_n_offset['lineno']
        res.col_offset = line_n_offset['col_offset']
        if childs and getattr(res, 'body', None) and isinstance(res.body[0], ast.Pass):
            res.body = list(childs) or []
        ast.fix_missing_locations(res)
        yield res


def parse_to_ast(filename):
    def parse_ast(ast, space=0):
        if not ast:
            return
        for line, block in ast:
            if not line:
                continue
            line_n_offset = {'lineno': 1, 'col_offset': 0}
            print(' ' * space, line)
            converter_name, (lineno, offset), *args = line
            converter = getattr(AstParsers, converter_name, None)
            if converter:
                yield from converter(*args, childs=parse_ast(block, space=space + 1), line_n_offset=line_n_offset)
    try:
        ast = func_parser().parse(tokenize(open(filename).readline))
    except NoParseError as e:
        print(e.__dict__)
        raise
    return list(parse_ast(ast))


def func_compile(filename):
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
            body=parse_to_ast(filename),
            decorator_list=[],
            returns=None,
        )],
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


def start_tag(name, *single_args, ** kwargs):
    attributes =' '.join(
        [tag_attribute(name, value) for name, value in kwargs.items()]
        + [escape(name) for name in single_args]
    )
    if attributes:
        return Markup('<{name} {attributes}>'.format(name=name.rstrip('/'), attributes=attributes))
    return Markup('<{}>'.format(name.rstrip('/')))


def stop_tag(name, *single_attrs, **kwargs):
    if name[-1] == '/':
        return ''
    return Markup('</{}>'.format(name))


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
            return ModuleSpec(fullname, TopLevelLoader(fullname, self.basepath), origin=path, is_package=True)
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
