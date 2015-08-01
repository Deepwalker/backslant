# Flask Jinja2 integration for backslant
from flask import current_app
from jinja2.environment import Template
from . import escaped, Markup


def extend_jinja2(name, **blocks):
    context_options = blocks.pop('context', {})
    template = current_app.jinja_env.get_or_select_template(name)
    current_app.update_template_context(context_options)
    context = template.new_context(context_options)
    for key, block in blocks.items():
        context.blocks[key] = [escaped(block)]
    for token in template.root_render_func(context):
        yield Markup(token)


def include_jinja2(name, options={}):
    template = current_app.jinja_loader.load(current_app.jinja_env, name)
    current_app.update_template_context(options)
    context = template.new_context(options)
    for token in template.root_render_func(context):
        yield Markup(token)


class BSTemplate(Template):
    def __new__(cls, *a, **kw):
        return object.__new__(cls)

    def __init__(self, bs_renderer):
        self.renderer = bs_renderer
        self.name = repr(bs_renderer)

    def root_render_func(self, context):
        if hasattr(self.renderer, 'render'):
            return self.renderer.render(context=context)
        return self.renderer(context=context)

    def new_context(self, vars, shared=False, locals=None):
        return dict(vars=vars, locals=locals)

