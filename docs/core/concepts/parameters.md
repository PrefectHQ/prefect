# Parameters

Parameters are special tasks that can receive user inputs whenever a flow is run.

```python
from prefect import task, Flow, Parameter

@task
def print_plus_one(x):
    print(x + 1)

with Flow('Parameterized Flow') as flow:
    x = Parameter('x')
    print_plus_one(x=x)

flow.run(parameters=dict(x=1)) # prints 2
flow.run(parameters=dict(x=100)) # prints 101
```

:::tip Parameter names
While parameters can have any name, there can only be one parameter with that name in the flow. This is achieved by requiring a `Parameter's` slug to be the same as its name.
:::

## Type-casting Parameter values

`Parameters` accept an optional keyword argument, `cast`, that can be used to modify its result. This is important because `Parameters` typically receive input as a string (via env var) or JSON (via API). To supply a cast function, simply provide it at initialization:

```python
import pendulum

@task
def print_one_year_later(x):
    print(x.add(years=1))

with Flow('Parameter casts') as flow:
    x = Parameter('x', cast=pendulum.parse)
    print_one_year_later(x)

flow.run(parameters=dict(x='2019-01-01')) # prints 2020-01-01T00:00:00+00:00
```
