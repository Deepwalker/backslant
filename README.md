Backslant
=========

Is a template engine built in completely other way then before.

First - you can use all python and more - you must use it if you want somwthing more
then just tags.

Second - it completely iterative. You can feed iterators or generators as input and get iterative output.

Third - it works through imports. If you want to get template just import it and use. If you want include
other template - import it. If you want template in some dir, import it! Like ```from . import other_template```.

So, with this principles in mind, you can try this proof of concept thing, due it is not complete:

    import backslant

    sys.meta_path.insert(0, backslant.PymlFinder('./templates', hook='backslant_import'))
    from backslant_import.home import index

    for chunk in index.render(title='The Real Thing'):
        print(chunk)

And templates/home/index.bs:

    html
        head
            title
                - yield options['title']
        body
            div.content
                h1
                    "Header"

I will complete feture set soon, stay tuned.
