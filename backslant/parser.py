from funcparserlib.parser import many, maybe, skip, some, forward_decl, NoParseError
from funcparserlib.lexer import Token


def combine(toks):
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


sometok = lambda s: some(lambda tok: tok.value == s)
sometype = lambda t: some(lambda tok: tok.type == t)
newline = skip(sometype('NEWLINE'))
name = sometype('NAME')
space = sometype('SPACE')
python_name = name + many(sometok('.') + name)
to_end_of_line = many(some(lambda token: token.type != 'NEWLINE')) >> combine
take_value = lambda tok: tok.value
skip_space = skip(maybe(space))

def paren_match(start, end=None):
    if not end:
        end = start
    parens = forward_decl()
    no_paren_dent_nl = some(lambda tok: not tok.value in (start, end))
    parens.define(sometok(start) + many(no_paren_dent_nl | parens) + sometok(end))
    return parens


python_call = (sometok('-') + skip_space + to_end_of_line) >> (lambda toks: ('python', toks[0].start, toks[1], tuple()))
python_yield_from_call = (skip(sometok('=')) + sometok('=') + skip_space + to_end_of_line) >> (lambda toks: ('python_yield_from', toks[0].start, toks[1]))
python_yield_call = (sometok('=') + skip_space + to_end_of_line) >> (lambda toks: ('python_yield', toks[0].start, toks[1]))


macro = (skip(sometok(':')) + sometype('NAME') + to_end_of_line) >> (lambda toks: ('macro', toks[0].start, toks[0].value, toks[1]))
string = (sometok('|') + to_end_of_line) >> (lambda tok: ('string', tok[0].start, tok[1]))
string = string | sometype('STRING') >> (lambda tok: ('string', tok.start, tok.value))
text = sometype('STRING') >> take_value


# HTML attr
html_name = name + many(sometok('-') + name)
html_name_str = html_name >> combine
attribute_value = (sometype('STRING') >> take_value) | ((paren_match('(', ')') | python_name) >> combine)
single_attr = html_name_str
pair_attr = (html_name_str + sometok('=') + attribute_value) >> (lambda toks: (toks[0], toks[2]))
attribute = pair_attr | single_attr
attributes = (
    ((sometok('(') + many(attribute + skip(maybe(space))) + sometok(')')) >> (lambda toks: toks[1]))
    | (paren_match('{', '}') >> combine)
)
tag_class = (sometok('.') + html_name_str) >> (lambda toks: ('class', toks[1]))
tag_id = skip(sometok('#')) + html_name_str >> (lambda tok: ('id', tok))
tag_name = (maybe(sometok('!')) + html_name + maybe(sometok('/'))) >> combine
tag = tag_name + many(tag_class | tag_id) + maybe(skip_space + attributes) + maybe(skip(space) + text) >> (lambda toks: ('tag', (0, 0), toks))


# lines and blocks
definition = (tag | python_yield_from_call | python_yield_call | python_call | macro | string)
line = forward_decl()
block = (skip(sometype('INDENT')) + many(line) + skip(sometype('DEDENT')))


# py blocks
def py_expr(name):
    expr = (sometok('-') + skip_space + sometok(name) + to_end_of_line) >> (lambda toks: ('python', toks[0].start, toks[1].value + toks[2]))
    return skip_space + expr + skip(newline) + block

def py_expr_combine(tok):
    return (tok[0] + (tok[2:],), tok[1])

block_for = py_expr('for') + maybe(py_expr('else'))
block_while = py_expr('while') + maybe(py_expr('else'))
block_if = py_expr('if') + many(py_expr('elif')) + maybe(py_expr('else'))
block_try = py_expr('try') + many(py_expr('except')) + maybe(py_expr('else')) + maybe(py_expr('finally'))
py_definition = (block_for | block_while | block_try | block_if) >> py_expr_combine


# try python blocks first
line.define(py_definition | (skip_space + maybe(definition) + newline + maybe(block)))


bs_parser = (many(line) + skip(sometype('END')))

