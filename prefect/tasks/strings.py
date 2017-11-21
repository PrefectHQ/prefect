from prefect.task import Task

class StringFormatterTask(Task):

    def __init__(self, template, **kwargs):
        self.template = template
        super().__init__(**kwargs)

    def run(self, **format_kwargs):
        return self.template.format(**format_kwargs)
