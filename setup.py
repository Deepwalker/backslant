#!/usr/bin/env python

from setuptools import setup
import os.path


def read(fname):
    try:
        return open(os.path.join(os.path.dirname(__file__), fname)).read()
    except IOError:
        return ''


setupconf = dict(
    name='backslant',
    version='0.1.2',
    license='BSD',
    url='https://github.com/Deepwalker/backslant/',
    author='Deepwalker',
    author_email='krivushinme@gmail.com',
    description='Python template engine.',
    long_description=read('README.md'),
    keywords='template ast jinja2 mako',

    install_requires=['pyparsing', 'markupsafe'],
    py_modules=['backslant'],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
    ]
)

if __name__ == '__main__':
    setup(**setupconf)
