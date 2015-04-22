# Flask Jinja2 integration for backslant

def jinja2_integration(application):
    def extend_jinja2(name, **blocks):
        context_options = blocks.pop('context', {})
        template = application.jinja_loader.load(application.jinja_env, name)
        application.update_template_context(context_options)
        context = template.new_context(context_options)
        for key, block in blocks.items():
            context.blocks[key] = [block]
        return template.root_render_func(context)


    def include_jinja2(name, options={}):
        template = application.jinja_loader.load(application.jinja_env, name)
        application.update_template_context(options)
        context = template.new_context(options)
        return template.root_render_func(context)

    return extend_jinja2, include_jinja2