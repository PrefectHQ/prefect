import prefect

NO_DEFAULT = '__NO_DEFAULT__'


class Parameter(prefect.tasks.core.ContextTask):
    """
    This class defines a Flow Parameter.

    Parameters are like ContextTasks in that they pull values from context,
    but Flows are aware of their Parameters and can broadcast them (or check
    if required parameters are supplied.)
    """

    def __init__(self, name, default=NO_DEFAULT):
        """
        Args:
            name (str): the Parameter name.

            default (any): A default value for the parameter. Parameters with no
                default are considered required. Note that `None` is a valid
                default value; to indicate no default pass the NO_DEFAULT
                variable.
        """
        self.default = default
        if self.default == NO_DEFAULT:
            default = prefect.utilities.functions.OPTIONAL_ARGUMENT
        super().__init__(
            context_key=name,
            name=name,
            autorename=False,
            missing_value=default,
            max_retries=None)


class RequiredParameter(Parameter):
    """
    A parameter that is explicitly required.
    """
    def __init__(self, name):
        super().__init__(name=name)
