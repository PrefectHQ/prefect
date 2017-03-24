_CONTEXT_MANAGER_FLOW = None


class Flow:

    def __init__(self, name, params=None, version=1):

        if not isinstance(name, str):
            raise TypeError(
                'Name must be a string; received {}'.format(type(name)))

        if params is None:
            params = {}

        self.name = name
        self.version = version
        self.params = params

        # a graph of task relationships keyed by the `after` task
        # and containing all the `before` tasks as values
        # { after : set(before, ...)}
        self.graph = {}

    @property
    def id(self):
        return '{}:{}'.format(self.name, self.version)

    # Tasks ---------------------------------------------------------

    def add_task(self, task):
        if task.flow.id != self.id:
            raise ValueError('Task {} is already in another Flow'.format(task))

        task_names = set(t.name for t in self.graph)
        if task.name in task_names:
            raise ValueError(
                'A task named {} already exists in this Flow.'.format(
                    task.name))
        self.graph[task] = set()

    def add_task_relationship(self, before, after):
        if before not in self.graph:
            self.add_task(before)
        if after not in self.graph:
            self.add_task(after)
        self.graph[after].add(before)

    # Context Manager -----------------------------------------------

    def __enter__(self):
        global _CONTEXT_MANAGER_FLOW
        self._old_context_manager_flow = _CONTEXT_MANAGER_FLOW
        _CONTEXT_MANAGER_FLOW = self
        return self

    def __exit__(self, _type, _value, _tb):
        global _CONTEXT_MANAGER_FLOW
        _CONTEXT_MANAGER_FLOW = self._old_context_manager_flow

    # /Context Manager ----------------------------------------------
