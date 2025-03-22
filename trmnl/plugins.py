from trmnl.time import current_time
from django.template.loader import get_template


class BasePlugin:
    def __init__(self, config):
        self.config = config

    def is_optional():
        return False

    def should_display():
        return True

    def generate_html(self):
        raise NotImplementedError

    def config_get(self, key: str):
        if key in self.config:
            return self.config[key]
        else:
            return None

    def __str__(self):
        return f"<Plugin {self.__class__.__name__}>"


class DefaultTemplatePlugin(BasePlugin):
    def template(self, context, data):
        context["SCREEN_DATA"] = data
        template = get_template("base_template.html")
        return template.render(context)

    def full(self, *args, **kwargs):
        argstr = "".join(args)
        titlebar = "" if kwargs.get("no_titlebar", False) else self.titlebar(*kwargs)
        return f"""<div class="view view--full">{argstr}{titlebar}</div>"""

    def titlebar(self, **kwargs):
        now = current_time(self.config_get("timezone"))
        generation_time = now.strftime("%A %H:%M")
        return f"""<div class="title_bar"><span class="title">{kwargs.get('title', "Plugin")}</span><span class="instance">{generation_time}</span></div>"""

    def col(self, data):
        return f"""<div class="layout layout--col gap--space-between">{data}</div>"""


class StaticHTMLPlugin(BasePlugin):
    def generate_html(self):
        return self.config["html"]
