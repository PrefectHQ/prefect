import prefect


class FunctionTask(prefect.Task):

    def __init__(self, fn, name=None, **kwargs):
        if not isinstance(fn, callable):
            raise TypeError('fn must be callable.')

        self.fn = fn

        # set the name from the fn
        if name is None:
            name = getattr(fn, '__name__', type(self).__name__)
            flow = prefect.context.get('flow')
            if flow:
                name = prefect.utilities.strings.name_with_suffix(
                    name=name,
                    delimiter='-',
                    first_suffix=2,
                    predicate=lambda n: n not in [t for t in flow.tasks])

        super().__init__(name=name, **kwargs)

    def run(self, **inputs):
        return self.fn(**inputs)


def task(self, fn=None, **kwargs):
    """
    A decorator for creating Tasks from functions.

    Usage:

    with Flow('flow') as f:

        @task
        def myfn():
            time.sleep(10)
            return 1

        @task(name='hello', retries=3)
        def hello():
            print('hello')

    """
    if callable(fn):
        return FunctionTask(fn=fn, flow=self)
    else:

        def wrapper(fn):
            return FunctionTask(fn=fn, flow=self, **kwargs)

        return wrapper
