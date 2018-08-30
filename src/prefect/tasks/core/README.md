# Core Task Classes

These Task classes are "core" in the sense that they are used elsewhere in Prefect. They include:

- `function.py`: the `FunctionTask` used for the `@task` decorator
- `operators.py`: used to implement `Task` magic methods and indexing
- `constants.py`: used to represent constant values
- `collections.py`: used to represent collections of tasks
