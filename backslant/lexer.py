from funcparserlib.lexer import make_tokenizer, Token
import re


ENCODING = 'utf-8'
regexps = {
    'escaped': r'''
        \\                                  # Escape
          ((?P<standard>["\\/bfnrt])        # Standard escapes
        | (u(?P<unicode>[0-9A-Fa-f]{4})))   # uXXXX
    ''',
    'unescaped': r'''
        [\x20-\x21\x23-\x5b\x5d-\uffff]     # Unescaped: avoid ["\\]
    ''',
    'ml_unescaped': r'''
        [\x01-\x21\x23-\uffff]
    ''',
}

specs = [
    ('STRING', (r'"""(%(ml_unescaped)s | %(escaped)s)*?"""' % regexps, re.VERBOSE | re.MULTILINE)),
    ('STRING', (r"'''(%(ml_unescaped)s | %(escaped)s)*?'''" % regexps, re.VERBOSE | re.MULTILINE)),
    ('NEWLINE', (r'[\r\n]+',)),
    ('SPACE', (r'[\s\f\t]+',)),
    ('STRING', (r'"([^\"] | %(escaped)s)*"' % regexps, re.VERBOSE)),
    ('STRING', (r"'([^\'] | %(escaped)s)*'" % regexps, re.VERBOSE)),
    ('OP', (r'[:.,*#|\-+=<>/!(){}\[\]]',)),
    ('NAME', (r'[^ \n\t\f:.,*#|\-+=<>/!(){}\[\]]+',)),
]
tokenizer = make_tokenizer(specs)

def idented_tokenizer(s):
    eol = False
    idents = [0]
    last_token = None
    for token in tokenizer(s):
        # print(token)
        last_token = token
        if token.type == 'NEWLINE':
            eol = True
            yield token
            continue
        if eol:
            value = token.value
            ident = len(value) - len(value.lstrip(' '))
            last = idents[-1]
            if ident > last:
                yield Token('INDENT', 'INDENT', start=token.start, end=token.end)
                idents.append(ident)
            while ident < last:
                yield Token('DEDENT', 'DEDENT', start=token.start, end=token.end)
                idents.pop()
                last = idents[-1]
        yield token
        eol = False
    if last_token.type != 'NEWLINE':
        yield Token('NEWLINE', '\n', start=last_token.end, end=last_token.end)
    for i in idents[1:]:
        yield Token('DEDENT', 'DEDENT', start=token.start, end=token.end)
    yield Token('END', '', start=token.start, end=token.end)


if __name__ == '__main__':
    for tok in idented_tokenizer(open('example/templates/test.bs').read()):
        if tok.type in ('INDENT', 'DEDENT'):
            print(tok)