import prefect
from prefect import Task

from .conditional import CompareValue


__all__ = ("case", "Variable")


class case(object):
    def __init__(self, value, case):
        if isinstance(case, Task):
            raise TypeError("`case` cannot be a task")

        self.value = value
        self.case = case
        self.children = set()

    def add_child(self, child):
        self.children.add(child)

    def __enter__(self):
        self.__prev_case = prefect.context.get("case")
        prefect.context.update(case=self)

    def __exit__(self, *args):
        if self.__prev_case is None:
            prefect.context.pop("case", None)
        else:
            prefect.context.update(case=self.__prev_case)

        if self.children:

            flow = prefect.context.get("flow", None)
            if not flow:
                raise ValueError("Could not infer an active Flow context.")

            cond = CompareValue(self.case, name=f"case({self.case})",).bind(
                value=self.value
            )

            for child in self.children:
                if not any(t in self.children for t in flow.upstream_tasks(child)):
                    child.set_upstream(cond)


class Variable(Task):
    def __init__(self, **kwargs):
        if kwargs.setdefault("skip_on_upstream_skip", False):
            raise ValueError("Variable tasks must have `skip_on_upstream_skip=False`.")
        kwargs.setdefault("trigger", prefect.triggers.not_all_skipped)
        self._input_counter = 0
        super().__init__(**kwargs)

    def set(self, task):
        i = self._input_counter
        self._input_counter += 1
        self.set_dependencies(keyword_tasks={"in_%d" % i: task})

    def run(self, **inputs):
        return next(
            (v for k, v in sorted(inputs.items(), reverse=True) if v is not None), None,
        )
