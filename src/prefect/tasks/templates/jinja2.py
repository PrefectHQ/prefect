from typing import Any

import prefect
from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs

try:
    from jinja2 import Template
except ImportError:
    raise ImportError(
        "Using `prefect.tasks.templates.jinja2` requires Prefect to be installed "
        "with the 'templates' extra."
    )


class JinjaTemplate(Task):
    """
    This task contains a Jinja template which is formatted with the results of any
    upstream tasks and returned.

    Variables from `prefect.context` will also be used for rendering.

    Args:
        - template (str, optional): the optional _default_ template string to render at runtime;
            can also be provided as a keyword to `run`, which takes precedence over this default.
        - **kwargs (optional): additional keyword arguments to pass to the
            standard Task constructor

    Example:

    ```python
    from prefect import Flow
    from prefect.tasks.templates import JinjaTemplate


    message = '''
    Hi {{name}}!  Welcome to Prefect.  Today is {{today}}.
    '''

    msg_task = JinjaTemplate(name="message body", template=message)

    with Flow("string-template") as flow:
            output = msg_task(name="Marvin")

    flow_state = flow.run()

    print(flow_state.result[output].result)
    # Hi Marvin!  Welcome to Prefect.  Today is 2019-08-28.
    ```
    """

    def __init__(self, template: str = None, **kwargs: Any):
        self.template = template or ""
        super().__init__(**kwargs)

    @defaults_from_attrs("template")
    def run(self, template: str = None, **format_kwargs: Any) -> str:
        """
        Formats the Jinja Template with the provided kwargs.

        Args:
            - template (str, optional): the template string to render; if not
                provided, `self.template` will be used
            - **format_kwargs (optional): keyword arguments to use for
                rendering; note that variables from `prefect.context` will also be used

        Returns:
            - str: the rendered string
        """
        template = Template(template)
        with prefect.context(**format_kwargs) as data:
            return template.render(**data)
