import sys
from backslant import PymlFinder, BackslantFinder


def print_render(func, *a, **kw):
    index = 0
    for chunk in func(title='The Incredible'):
        if chunk.startswith('</'):
            index = index - 1
        print('    ' * index, chunk)
        if chunk.startswith('<') and not chunk.startswith('</'):
            index = index + 1


sys.meta_path.insert(0, PymlFinder('example'))
import backslant_hook.templates.test as test
index = 0
print_render(test.render, title='The Incredible')

import backslant_hook.templates.index as index
print_render(index.render)

print('Test hook less importer')
sys.meta_path.insert(0, BackslantFinder())
from example import package_import_test
print_render(package_import_test.render)