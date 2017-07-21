"""
This module implements the Prefect context that is available when tasks run.

Tasks can import prefect.context and access attributes that will be overwritten
when the task is run.

>>> Example

Example:
    import prefect.context
    with prefect.context(a=1, b=2):
        print(prefect.context.a) # 1
    print (prefect.context.a) # undefined

"""
from contextlib import contextmanager as _contextmanager
import threading


# context dictionary
class Context(threading.local):
    """
    A context store for Prefect data.
    """

    def __init__(self, *args, **kwargs):
        self.reset(*args, **kwargs)

    def __repr__(self):
        return '<PrefectContext>'

    def __iter__(self):
        return iter(self.__dict__.keys())

    def __getitem__(self, key):
        return getattr(self, key)

    def to_dict(self):
        return self.__dict__.copy()

    def update(self, *args, **kwargs):
        if args == (None,):
            args = ()
        self.__dict__.update(*args, **kwargs)

    def reset(self, *args, **kwargs):

        self.__dict__.clear()

        # set the following properties to assist with autocomplete tools
        # -- they don't actually do anything until context is set

        self.run_dt = None
        self.as_of_dt = None

        self.flow = None
        self.flow_id = None
        self.flow_project = None
        self.flow_name = None
        self.flow_version = None
        self.flow_state = None
        self.params = None

        self.flowrun_start_tasks = set()

        self.task_id = None
        self.task_name = None
        self.task_state = None

        self.run_number = None

        self.update(*args, **kwargs)

    @_contextmanager
    def __call__(self, *context_args, **context_kwargs):
        """
        A context manager for setting / resetting the Prefect context

        Example:
            import prefect.context
            with prefect.context(dict(a=1, b=2), c=3):
                print(prefect.context.a) # 1
        """
        previous_context = self.to_dict()
        try:
            self.update(*context_args, **context_kwargs)
            yield self
        finally:
            self.reset(previous_context)

    def get(self, key, missing_value=None):
        return getattr(self, key, missing_value)


context = Context()
