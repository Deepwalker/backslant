# Flask Jinja2 integration for backslant
from flask import current_app

def extend_jinja2(name, **blocks):
    context_options = blocks.pop('context', {})
    template = current_app.jinja_loader.load(current_app.jinja_env, name)
    current_app.update_template_context(context_options)
    context = template.new_context(context_options)
    for key, block in blocks.items():
        context.blocks[key] = [block]
    return template.root_render_func(context)


def include_jinja2(name, options={}):
    template = current_app.jinja_loader.load(current_app.jinja_env, name)
    current_app.update_template_context(options)
    context = template.new_context(options)
    return template.root_render_func(context)