---
sidebarDepth: 0
---
# Scaling Out

::: tip Follow along in the Terminal

```
cd examples/tutorial
python 06_parallel_execution.py
```

:::

Let's adjust our `Flow` to distribute its `Tasks` onto a [Dask](https://dask.org/) Cluster, parallelizing its execution. This may sound involved, but will actually be our simplest adjustment yet:

```python{1,7}
from prefect.executors import DaskExecutor

# ...task definitions...

# ...flow definition...
if __name__=="__main__":
    flow.run(executor=DaskExecutor())
```

This will spin up a [Local Dask Cluster](https://docs.dask.org/en/latest/setup/single-distributed.html) on your system to parallelize the tasks. If you already have a Dask Cluster deployed elsewhere, you can leverage that cluster by specifying the address in the `DaskExecutor` constructor:

```python{3}
flow.run(
    executor=DaskExecutor(
        address='some-ip:port/to-your-dask-scheduler'
    )
)
```

Furthermore, you can implement your own `Executor` for use with any Prefect `Flow`, as long as the object provided satisfies [the `Executor` interface](https://github.com/PrefectHQ/prefect/blob/master/src/prefect/executors/base.py) (i.e. appropriate `submit`, `map`, and `wait` functions, similar to Python's [`concurrent.futures.Executor`](https://docs.python.org/3/library/concurrent.futures.html#executor-objects) interface). In this way, the sky is the limit!

::: warning Up Next!

What else can Prefect do?...

:::
