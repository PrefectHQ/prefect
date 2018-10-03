# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from jinja2 import Template
from typing import Any

import prefect
from prefect import Task


class JinjaTemplateTask(Task):
    """
    This task contains a Jinja template which is formatted with the results of any
    upstream tasks and returned.

    Variables from `prefect.context` are also available for rendering.
    """

    def __init__(self, template: str = None, **kwargs: Any) -> None:
        self.template = Template(template or "")
        super().__init__(**kwargs)

    def run(self, template: str = None, **format_kwargs: Any) -> str:  # type: ignore
        if template is None:
            template = self.template
        with prefect.context(**format_kwargs) as data:
            return template.render(**data)


class StringFormatterTask(Task):
    """
    This task contains a template which is formatted with the results of any
    upstream tasks and returned.

    Variables from `prefect.context` are also available for formatting.
    """

    def __init__(self, template: str = None, **kwargs: Any) -> None:
        self.template = template or ""
        super().__init__(**kwargs)

    def run(self, template: str = None, **format_kwargs: Any) -> str:  # type: ignore
        if template is None:
            template = self.template
        with prefect.context(**format_kwargs) as data:
            return template.format(**data)
