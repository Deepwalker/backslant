Backslant
=========

Is a template engine built in completely other way then before.

First - you can use all python and you must use it if you want something more
then just tags.

Second - it completely iterative. You can feed iterators or generators as input and get iterative output.

Third - it works through imports. If you want to get template just import it and use. If you want include
other template - import it. If you want template in some dir, import it! Like ```from . import other_template```.
Use absolute or relative imports.

So, with this principles in mind, you can try this proof of concept thing, due it is not complete:

    import backslant

    sys.meta_path.insert(0, backslant.PymlFinder('./templates', hook='mypkg.templates'))
    from mypkg.templates.home import index

    for chunk in index.render(title='The Real Thing'):
        print(chunk)

And templates/home/index.bs:

    html
        head
            title
                - yield options['title']
        body
            div.content#content
                h1#header "Header"

You can define a function:

    - def render_form(method):
        form method=method
            input(type="text" value="123")

End call it:

    h1
        - yield from render_form('POST')

Yes, its this simple, you just use python constructions. And for now inheritance of templates
you can made just with function.

base.bs:

    !doctype/ html
    html
    head
        title "Page Title"
    body
        h1{'class': ' '.join(['main', 'content'], 'ng-app': 'Application'}
            | Page Header
        div.content
            - yield from options['content_block']()
        div.footer
            | Backslant © 2015

index.bs:

    - from . import base
    - def content():
        - for i in range(10):
            p
                - yield 'Paragraph {}'.format(i)
    - yield from base.render(content_block=content)

I think about adding something like ruby blocks or something to made this a bit more simpler, but
what can be more simple then functions define and call?

But we have syntax sugar for this:

    :call base.render(*options)
        :content_block
            - for i in range(10):
                p
                    - yield 'Paragraph {}'.format(i)
        :footer_block
            p "Index page"

Arguments
---------

To define tag arguments you can use arg=`parentised python expression or variable name` or `tag.class {'a': 5, 'b': ' '.join(options.classes)}` form.


Render or not render?
---------------------

When template compiled, we need it to place in module somehow. If you have any tags  or calls in top level, then we definitely must place them into function. And we create `render` function for this purpose. Then you import template and call this `render`.

But if you have not in top level, then will yield anything, then function is not needed - you can create library file.
So - if you template on top level only defines functions and imports, then backslant will not implicitly cover it in `render` function, and this is way to define your template libs.


Afterwords
----------

I have completed examples with flask and http.server in examples folder. And you can compare perfomance with jinja2. Its almost equal.

I will complete feature set soon, stay tuned.
