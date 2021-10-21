# Testing Prefect flows and tasks

Since Prefect flows are Python objects they can be tested in any way you would normally test your Python code! This means that it is common for users to test their flows in unit tests with libraries like [pytest](https://docs.pytest.org/en/latest/). Below runs through a few ways to test your flows and if you want further examples Prefect's [tests directory](https://github.com/PrefectHQ/prefect/tree/master/tests) has thousands of tests that could serve as inspiration for testing your [flows](https://github.com/PrefectHQ/prefect/blob/master/tests/core/test_flow.py) and [tasks](https://github.com/PrefectHQ/prefect/blob/master/tests/core/test_task.py).

Use the following flow as an example:

:::: tabs
::: tab Functional API
```python
from prefect import task, Flow

@task
def extract():
    return 10

@task
def transform(x):
    return x + 10

@task
def load(x):
    print(x)

with Flow("testing-example") as flow:
    e = extract()
    t = transform(e)
    l = load(t)
```
:::

::: tab Imperative API
```python
from prefect import Task, Flow

class Extract(Task):
    def run(self):
        return 10

class Transform(Task):
    def run(self, x):
        return x + 10

class Load(Task):
    def run(self, x):
        print(x)

flow = Flow("testing-example")

e = Extract()
t = Transform()
l = Load()

flow.add_edge(upstream_task=e, downstream_task=t, key="x")
flow.add_edge(upstream_task=t, downstream_task=l, key="x")
```
:::
::::

#### Testing flow composition

```python
from prefect.core.edge import Edge

assert e in flow.tasks
assert t in flow.tasks
assert l in flow.tasks
assert len(flow.tasks) == 3

assert flow.root_tasks() == set([e])
assert flow.terminal_tasks() == set([l])

assert len(flow.edges) == 2
assert Edge(upstream_task=e, downstream_task=t, key="x") in flow.edges
assert Edge(upstream_task=t, downstream_task=l, key="x") in flow.edges
```

#### Testing state

```python
state = flow.run()

assert state.is_successful()
assert state.result[e].is_successful()
assert state.result[t].is_successful()
assert state.result[l].is_successful()
```

#### Testing results

```python
state = flow.run()

assert state.result[e].result == 10
assert state.result[t].result == 20
assert state.result[l].result == None
```