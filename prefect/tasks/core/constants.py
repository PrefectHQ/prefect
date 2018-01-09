import prefect


class Constant(prefect.Task):

    def __init__(self, value, name=None, autorename=True, **kwargs):

        self.value = value

        # set the name from the fn
        if name is None:
            name = 'Constant[{type}]'.format(type=type(value).__name__)
            autorename = True

        super().__init__(name=name, autorename=autorename, **kwargs)

    def run(self):
        return self.value


class ContextTask(prefect.Task):

    def __init__(
            self,
            context_key,
            name=None,
            if_missing=None,
            fail_if_missing=False,
            **kwargs):
        """

        A Task that retrieves a value from the active Prefect context.

        Args: context_key (str): the context key whose value will be returned

            name (str): an optional name for the task

            if_missing (any): a value to return if the context_key is not found
                in the context.

            fail_if_missing (bool): if True, the task will fail if the
                context_key is not found in the context (regardless of whether
                an if_missing value is supplied)

        """
        self.context_key = context_key
        self.if_missing = if_missing
        self.fail_if_missing = fail_if_missing

        if name is None:
            name = 'Context["{}"]'.format(context_key)
            kwargs['autorename'] = True

        super().__init__(name=name, **kwargs)

    def run(self):
        context = prefect.context.Context
        if self.fail_if_missing and self.context_key not in context:
            raise prefect.signals.FAIL(
                '"{}" was not found in the Prefect context.'.format(
                    self.context_key))
        return context.get(self.context_key, self.if_missing)


class Parameter(prefect.Task):
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
