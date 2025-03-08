from typing import override


class BasePlugin:
    def __init__(self, config):
        self.config = config

    def generate_html(self):
        raise NotImplementedError

    def __str__(self):
        return f"<Plugin {self.__class__.__name__}>"


from django.template.loader import get_template


class DefaultTemplatePlugin(BasePlugin):
    def template(self, context, data):
        context["SCREEN_DATA"] = data
        template = get_template("base_template.html")
        return template.render(context)


class StaticHTMLPlugin(BasePlugin):
    def generate_html(self):
        return self.config["html"]
