from prefect.tasks.templates.strings import StringFormatterTask

try:
    from prefect.tasks.templates.jinja2 import JinjaTemplateTask
except ImportError:
    pass
