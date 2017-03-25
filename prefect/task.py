import datetime
import prefect.flow
import prefect.triggers


class Task:
    """
    Tasks are basic units of work. Each task performs a specific funtion.
    """

    def __init__(
            self,
            fn,
            flow=None,
            name=None,
            params=None,
            retries=0,
            retry_delay=datetime.timedelta(minutes=5),
            trigger=None):
        self.fn = fn

        if flow is None:
            flow = prefect.flow._CONTEXT_MANAGER_FLOW
            if flow is None:
                raise ValueError(
                    'Tasks must be created with a Flow or inside '
                    'a Flow context manager.')
        self.flow = flow

        if name is None:
            name = self.fn.__name__

        if not isinstance(name, str):
            raise TypeError(
                'Name must be a string; received {}'.format(type(name)))
        self.name = name

        if not isinstance(retries, int):
            raise TypeError(
                'Retries must be an int; received {}'.format(retries))
        self.retries = retries

        if not isinstance(retry_delay, datetime.timedelta):
            raise TypeError(
                'Retry delay must be a timedelta; received {}'.format(
                    type(retry_delay)))
        self.retry_delay = retry_delay

        if trigger is None:
            trigger = prefect.triggers.all_success
        self.trigger = trigger

        #TODO params come from Flow
        self.params = params

        self.flow.add_task(self)

    def run(self):
        return self.fn()

    def id(self):
        return '{}:{}'.format(self.flow.id, self.name)

    def run_before(self, *tasks):
        """
        Adds a relationship to the Flow so that this task runs before another
        task.
        """
        for t in tasks:
            self.flow.add_task_relationship(before=self, after=t)

    def run_after(self, *tasks):
        """
        Adds a relationship to the Flow so that this task runs after another
        task.
        """
        for t in tasks:
            self.flow.add_task_relationship(before=t, after=self)

    # Sugar ---------------------------------------------------------

    def __or__(self, task):
        """ self | task -> self.run_before(task)"""
        self.run_before(task)

    def __rshift__(self, task):
        """ self >> task -> self.run_before(task)"""
        self.run_before(task)

    def __lshift__(self, task):
        """ self << task -> self.run_after(task)"""
        self.run_after(task)
