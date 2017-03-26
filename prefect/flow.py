import prefect.exceptions

_CONTEXT_MANAGER_FLOW = None


class Flow:

    def __init__(
            self,
            name,
            params=None,
            namespace=prefect.config.get('flows', 'default_namespace'),
            version=1,
            active=prefect.config.getboolean('flows', 'default_active')):

        if not isinstance(name, str):
            raise TypeError(
                'Name must be a string; received {}'.format(type(name)))

        if params is None:
            params = {}

        self.name = name
        self.namespace = namespace
        self.version = version
        self.params = params
        self.active = active

        # a graph of task relationships keyed by the `after` task
        # and containing all the `before` tasks as values
        # { after : set(before, ...)}
        self.graph = {}

    @property
    def id(self):
        if self.namespace:
            namespace = '{}.'.format(self.namespace)
        else:
            namespace = ''
        return '{}{}:{}'.format(namespace, self.name, self.version)

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

        # try sorting tasks to make sure there are no cycles (an error is
        # raised otherwise)
        self.sorted_tasks()


    def sorted_tasks(self):
        """
        Returns a topological sort of this Flow's tasks.

        Note that the resulting sort will not always be in the same order!
        """

        graph = self.graph.copy()
        sorted_graph = []

        while graph:
            acyclic = False
            for node in list(graph):
                for preceding_node in graph[node]:
                    if preceding_node in graph:
                        # the previous node hasn't been sorted yet, so
                        # this node can't be sorted either
                        break
                else:
                    # all previous nodes are sorted, so this one can be
                    # sorted as well
                    acyclic = True
                    del graph[node]
                    sorted_graph.append(node)
            if not acyclic:
                # no nodes matched
                raise prefect.exceptions.PrefectError(
                    'Cycle detected in graph!')


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
