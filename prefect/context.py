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

# ---------------------------------------------------------------------
# Context Functions
#
# These functions should be overwritten by executor-specific versions
# ---------------------------------------------------------------------


def progress(n, total=1):
    """
    Simple progress function.
    """
    pass


def submit_task(task, block=False):
    """
    Submit a task for execution.

    Args:
        task (Task): a task to run
        block (bool): if True, the call will block until the task is
            complete and return its state. Otherwise the task will be
            run asynchronously. Note that some executors do not support
            asynchronous execution.
    """
    pass


def submit_flow(flow, block=False):
    """
    Args:
        flow (Flow): a flow to run
        block (bool): if True, the call will block until the flow is
            complete and return its state. Otherwise the flow will be
            run asynchronously. Note that some executors do not support
            asynchronous execution.
    """
    pass


# context dictionary
class Context(threading.local):
    """
    A context store for Prefect data.
    """

    def __init__(self, **kwargs):
        self.reset(**kwargs)

    def __repr__(self):
        return '<PrefectContext>'

    def __iter__(self):
        return iter(self.__dict__.keys())

    def __getitem__(self, key):
        return getattr(self, key)

    def to_dict(self):
        return self.__dict__.copy()

    def update(self, **kwargs):
        self.__dict__.update(kwargs)

    def reset(self, **kwargs):

        self.__dict__.clear()

        # set the following properties to assist with autocomplete tools
        # -- they don't actually do anything until context is set

        self.run_dt = None
        self.as_of_dt = None

        self.flow = None
        self.flow_id = None
        self.flow_namespace = None
        self.flow_name = None
        self.flow_version = None
        self.flow_state = None
        self.params = None

        self.task_id = None
        self.task_name = None
        self.task_state = None

        self.run_number = None
        self.progress = progress
        self.submit_task = submit_task
        self.submit_flow = submit_flow

        self.update(**kwargs)

    @_contextmanager
    def __call__(self, **context):
        """
        A context manager for setting / resetting the Prefect context

        Example:
            import prefect.context
            with prefect.context(a=1, b=2):
                print(prefect.context.a) # 1
        """
        previous_context = self.to_dict()
        try:
            self.update(**context)
            yield self
        finally:
            self.reset(**previous_context)


context = Context()
