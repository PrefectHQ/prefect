import prefect


class Constant(prefect.Task):

    def __init__(self, value, name=None, **kwargs):

        self.value = value

        # set the name from the value
        if name is None:
            try:
                name = repr(self.value)
            except ValueError:
                name = 'Constant[{}]'.format(type(value).__name__)

        super().__init__(name=name, **kwargs)

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


