import prefect


class Constant(prefect.Task):
    def __init__(self, value, name=None, **kwargs):

        self.value = value

        # set the name from the value
        if name is None:
            name = repr(self.value)
            if len(name) > 8:
                name = "Constant[{}]".format(type(self.value).__name__)

        super().__init__(name=name, **kwargs)

    def run(self):
        return self.value
