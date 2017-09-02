import functools
import prefect


class FunctionTask(prefect.Task):

    def __init__(self, fn, name=None, **kwargs):
        if not callable(fn):
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
                    predicate=lambda n: n not in flow.tasks)

        super().__init__(name=name, **kwargs)

    def run(self, **inputs):
        return prefect.context.call_with_context_annotations(self.fn, **inputs)


def as_task(fn=None, **kwargs):
    """
    A decorator for creating Tasks from functions.

    Usage:

    @as_task
    def myfn():
        time.sleep(10)
        return 1

    @as_task(name='hello', retries=3)
    def hello():
        print('hello')

    with Flow() as flow:
        hello().run_before(myfn())

    """

    if callable(fn):
        return functools.partial(FunctionTask, fn=fn)
    else:

        def wrapper(fn):
            return functools.partial(FunctionTask, fn=fn, **kwargs)

        return wrapper
