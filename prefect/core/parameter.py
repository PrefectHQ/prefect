import prefect
from prefect.core.task import Task


class Parameter(Task):
    """
    This class defines a Flow Parameter.

    Parameters are like ContextTasks in that they pull values from context,
    but Flows are aware of their Parameters and can broadcast them (or check
    if required parameters are supplied.)
    """

    def __init__(self, name, default=None, required=True):
        """
        Args:
            name (str): the Parameter name.

            required (bool): If True, the Parameter is required and the default
                value is ignored.

            default (any): A default value for the parameter. If the default
                is not None, the Parameter will not be required.
        """
        if default is not None:
            required = False

        self.required = required
        self.default = default

        super().__init__(name=name, max_retries=None, autorename=False)

    def run(self):
        params = prefect.context.Context.get('parameters', {})
        if self.required and self.name not in params:
            raise prefect.signals.FAIL(
                'Parameter "{}" was required but not provided.'.format(
                    self.name))
        return params.get(self.name, self.default)
