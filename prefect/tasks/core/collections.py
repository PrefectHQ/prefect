from prefect import Task


class VarArgsTask(Task):
    def __call__(self, *args):
        """
        Accepts *args and transforms them into **kwargs
        """
        kwargs = {"arg_{}".format(i + 1): a for i, a in enumerate(args)}
        return super().__call__(**kwargs)


class List(VarArgsTask):
    def run(self, **task_results):
        return list(task_results.values())


class Set(VarArgsTask):
    def run(self, **task_results):
        return set(task_results.values())


class Tuple(VarArgsTask):
    def run(self, **task_results):
        return tuple(task_results.values())


class Dict(Task):
    def run(self, *, base_dict=None, **task_results):
        result = {}
        result.update(base_dict or {})
        result.update(task_results)
        return result
