import inspect
import pytest
import re
from prefect.core import Task
from prefect.tasks.toloka import operations as tlk


TASKS = {name: getattr(tlk, name)
         for name in dir(tlk)
         if isinstance(getattr(tlk, name), Task)}


@pytest.mark.parametrize('task_name', list(TASKS))
def test_all_arguments_documented(task_name):
    task = TASKS[task_name]
    args_doc = task.__doc__.split('    Args:\n')[1]

    non_documented = []
    for arg, param in inspect.signature(task).parameters.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            pattern = '^\\s+- \*\*kwargs[ :].+'  # noqa
        else:
            pattern = f'^\\s+- {arg} .+'
        if not re.search(pattern, args_doc, flags=re.MULTILINE):
            non_documented.append(arg)
    if non_documented:
        raise ValueError(f'Task {task_name} has undocummented args: {non_documented}')
