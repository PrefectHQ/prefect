import prefect


class ConstantTask(prefect.Task):

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
            missing_value=prefect.utilities.functions.OPTIONAL_ARGUMENT,
            autorename=True,
            **kwargs):
        """

        A Task that retrieves a value from the active Prefect context.

        Args:
            context_key (str): the context key whose value will be returned

            name (str): an optional name for the task

            missing_value (any): the value to supply if the key is not found
                in the Context

        """
        self.context_key = context_key
        self.missing_value = missing_value

        if name is None:
            name = 'Context["{}"]'.format(context_key)
            autorename = True

        super().__init__(name=name, autorename=autorename, **kwargs)

    def run(self):
        return prefect.context.Context.get(
            self.context_key,
            missing_value=self.missing_value)
