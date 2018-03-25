import prefect
import inspect


class FunctionTask(prefect.Task):

    def __init__(self, fn, name=None, **kwargs):
        if not callable(fn):
            raise TypeError('fn must be callable.')

        # set the name from the fn
        if name is None:
            name = getattr(fn, '__name__', type(self).__name__)

        if inspect.getfullargspec(fn).varargs:
            raise ValueError(
                'Tasks with variable positional arguments (*args) are not '
                'supported, because all Prefect arguments are stored as '
                'keywords. As a workaround, consider modifying the function '
                'to accept **kwargs and feeding the values '
                'to the original function\'s *args.')

        self.fn = fn
        self.run = prefect.context.apply_context_annotations(fn)

        super().__init__(name=name, **kwargs)
