# Parameters

Parameters are special tasks that can receive user inputs whenever a flow is run. Setting a default is optional. 

```python
from prefect import task, Flow, Parameter

@task
def print_plus_one(x):
    print(x + 1)

with Flow('Parameterized Flow') as flow:
    x = Parameter('x', default = 2)
    print_plus_one(x=x)

flow.run(parameters=dict(x=1)) # prints 2
flow.run(parameters=dict(x=100)) # prints 101
flow.run() #prints 3
```

!!! tip Parameter names
    While parameters can have any name, there can only be one parameter with that name in the flow. This is achieved by requiring a `Parameter's` slug to be the same as its name.

