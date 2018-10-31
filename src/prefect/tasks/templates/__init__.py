# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from prefect.tasks.templates.strings import StringFormatterTask

try:
    from prefect.tasks.templates.jinja2 import JinjaTemplateTask
except ImportError:
    pass
