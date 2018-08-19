# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from prefect import Task


class StringFormatterTask(Task):
    """
    This task contains a template which is formatted with the results of any
    upstream tasks and returned.
    """

    def __init__(self, template=None, **kwargs):
        self.template = template or ""
        super().__init__(**kwargs)

    def run(self, template=None, **format_kwargs):
        if template is None:
            template = self.template
        return template.format(**format_kwargs)
