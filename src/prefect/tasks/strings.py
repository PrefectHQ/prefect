# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from typing import Any

from prefect import Task


class StringFormatterTask(Task):
    """
    This task contains a template which is formatted with the results of any
    upstream tasks and returned.
    """

    def __init__(self, template: str = None, **kwargs: Any) -> None:
        self.template = template or ""
        super().__init__(**kwargs)

    def run(self, template: str = None, **format_kwargs: Any) -> str:  # type: ignore
        if template is None:
            template = self.template
        return template.format(**format_kwargs)
