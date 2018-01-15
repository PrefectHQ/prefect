import functools
import prefect


class FunctionTask(prefect.Task):

    def __init__(self, fn, name=None, **kwargs):
        if not callable(fn):
            raise TypeError('fn must be callable.')

        self.fn = fn

        # set the name from the fn
        if name is None:
            kwargs['autorename'] = True
            name = getattr(fn, '__name__', type(self).__name__)

        super().__init__(name=name, **kwargs)

    def run(self, **inputs):
        return prefect.context.call_with_context_annotations(self.fn, **inputs)

