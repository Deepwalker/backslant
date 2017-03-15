Backslant
=========

[![PyPI](https://img.shields.io/pypi/v/backslant.svg?style=flat-square)](https://pypi.python.org/pypi/backslant)
[![PyPI](https://img.shields.io/pypi/l/backslant.svg?style=flat-square)](https://pypi.python.org/pypi/backslant)

The Backslant is a template engine that was built completely other way then before.

First - you can use all python and you must use it if you want something more
then just tags.

Second - it completely iterative. You can feed iterators or generators as input and get iterative output.

Third - it works through imports. If you want to get template just import it and use. If you want include
other template - import it. If you want template in some dir, import it! Like ```from . import other_template```.
Use absolute or relative imports.

So, with this principles in mind, you can try backslant:

    import backslant
    # you need create __init__.py in templates folder to make this work
    sys.meta_path.insert(0, backslant.BackslantFinder())

    from mypkg.templates.home import index

    for chunk in index.render(title='The Real Thing'):
        print(chunk)

Or, if you want send rendered html to browser:

    from backslant import to_string
    to_string(index.render(title='The Real Thing'))

And templates/home/index.bs:

    html
        head
            title
                = options['title']
        body
            div.content#content
                h1#header "Header"

You can define a function:

    - def render_form(method):
        form(method=method)
            input(type="text" value="123")

End call it:

    h1
        == render_form('POST')

Yes, its this simple, you just use python constructions. There `==` is shotrcut for `- yield from`.
And `=` is a shortcut for `- yield`.

And for now inheritance of templates you can made just with function.

base.bs:

    !doctype/ html
    html
    head
        title "Page Title"
    body
        h1{'class': ' '.join(['main', 'content'], 'ng-app': 'Application'}
            | Page Header
        div.content
            == options['content_block']()
        div.footer
            | Backslant © 2015

index.bs:

    - from . import base
    - def content():
        - for i in range(10):
            p
                = 'Paragraph {}'.format(i)
    == base.render(content_block=content)

I think about adding something like ruby blocks or something to made this a bit more simpler, but
what can be more simple then functions define and call?

But we have syntax sugar for this:

    :call base.render(*options)
        :content_block
            - for i in range(10):
                p
                    = 'Paragraph {}'.format(i)
        :footer_block
            p "Index page"

Arguments
---------

To define tag arguments you can use arg=`parentised python expression or variable name` or
`tag.class {'a': 5, 'b': ' '.join(options.classes)}` form.


Render or not render?
---------------------

When template compiled, we need it to place in module somehow. If you have any tags or calls in top level,
then we definitely must place them into function. And we create `render` function for this purpose.
Then you import template and call this `render`.

But if you have not in top level, then will yield anything, then function is not needed - you can create library file.
So - if you template on top level only defines functions and imports, then backslant will not implicitly cover
it in `render` function, and this is the way to define your template libs. You can even distribute it on PyPi.


Flask
-----

If you want to integrate backslant into existing project, it can be painful to rewrite all templates. So
we have workaround:

    from backslant.flask import extend_jinja2, include_jinja2

And call it in template:

    - from backslant.flask import extend_jinja2, include_jinja2

    :call extend_jinja2('layouts/base.html')
        - def content(ctx):
            == include_jinja2('layouts/header.html')
            div.container
                div.page-header
                    h1
                        = options['company'].alias


Afterwords
----------

I have completed examples with flask and http.server in examples folder. And you can compare perfomance with jinja2.
Its almost equal.

I will complete feature set soon, stay tuned.
