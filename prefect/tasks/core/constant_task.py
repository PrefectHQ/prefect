import prefect


class ConstantTask(prefect.Task):

    def __init__(self, value, name=None, **kwargs):

        self.value = value

        # set the name from the fn
        if name is None:
            kwargs['autorename'] = True
            name = 'Constant[{type}]'.format(type=type(value))

        super().__init__(name=name, **kwargs)

    def run(self):
        return self.value
