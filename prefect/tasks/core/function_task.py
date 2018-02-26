import prefect
import inspect

class FunctionTask(prefect.Task):

    def __init__(self, fn, name=None, **kwargs):
        if not callable(fn):
            raise TypeError('fn must be callable.')

        self.fn = fn

        # set the name from the fn
        if name is None:
            name = getattr(fn, '__name__', type(self).__name__)

        super().__init__(name=name, **kwargs)

    def __call__(self, *args, _wait_for=None, **kwargs):
        signature = inspect.signature(self.fn)
        # try to bind arguments
        signature.bind(*args, **kwargs).arguments
        return super().__call__(self, *args, _wait_for, **kwargs)

    def run(self, *args, **inputs):
        return prefect.context.call_with_context_annotations(
            self.fn, *args, **inputs)
