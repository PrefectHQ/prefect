import prefect


class ConstantTask(prefect.Task):

    def __init__(self, value, name=None, autorename=True, **kwargs):

        self.value = value

        # set the name from the fn
        if name is None:
            name = 'Constant[{type}]'.format(type=type(value).__name__)

        super().__init__(name=name, autorename=autorename, **kwargs)

    def run(self):
        return self.value


class ContextTask(ConstantTask):

    def __init__(
            self,
            context_key,
            name=None,
            missing_value=None,
            raise_if_missing=False,
            autorename=True,
            **kwargs):
        """

        Args:
            context_key (str): the context key whose value will be returned

            name (str): an optional name for the task

            missing_value (any): the value to supply if the key is not found
                in the Context

            raise_if_missing (bool): if True, a bad context value will raise
                a ContextError

        """
        self.missing_value = missing_value
        self.raise_if_missing = raise_if_missing

        if name is None:
            name = 'Context["{}"]'.format(context_key)
            kwargs['autorename'] = True

        super().__init__(
            value=context_key, name=name, autorename=autorename, **kwargs)

    def run(self):
        return prefect.context.Context.get(
            self.value,
            missing_value=self.missing_value,
            raise_if_missing=self.raise_if_missing)
