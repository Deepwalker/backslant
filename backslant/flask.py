# Flask Jinja2 integration for backslant
from importlib import import_module

from flask import current_app
import jinja2
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

    def _uptodate(self):
        return True

    def root_render_func(self, context):
        if hasattr(self.renderer, 'render'):
            return self.renderer.render(context=context)
        return self.renderer(context=context)

    def new_context(self, vars, shared=False, locals=None):
        return dict(vars=vars, locals=locals)


class BackslantJinjaLoader():
    def __init__(self, top_jinja_loader):
        self.top_jinja_loader = top_jinja_loader
        self.cache_module = {}

    def try_module(self, name):
        module = self.cache_module.get(name)
        if module:
            return module
        try:
            module = import_module(name)
            self.cache_module[name] = module
        except ImportError:
            pass
        return module

    def get_source(self, environment, template):
        module = self.try_module(template)
        if module:
            return 'Source Of Module', template, None
        return self.top_jinja_loader.get_source(environment, template)

    def load(self, environment, name, globals=None):
        module = self.try_module(name)
        if module:
            return BSTemplate(module)
        return self.top_jinja_loader.load(environment, name, globals)
