# Parallel Execution

::: tip Follow along in the Terminal

```
cd examples/tutorial
python 06_parallel_execution.py
```

:::

Let's adjust our `Flow` to distribute its `Tasks` onto a [Dask](https://dask.org/) Cluster, parallelizing its execution. This may sound involved, but will actually be our simplest adjustment yet:

```python{1,7}
from prefect.engine.executors import DaskExecutor

# ...task definitions...

# ...flow definition...

flow.run(executor=DaskExecutor())
```

This will spin up a [Local Dask Cluster](http://distributed.dask.org/en/latest/local-cluster.html) on your system to parallelize the tasks. If you already have a Dask Cluster deployed elsewhere, you can leverage that cluster by specifying the address in the `DaskExecutor` constrictor:

```python{3}
flow.run(
    executor=DaskExecutor(
        address='some-ip:port/to-your-dask-scheduler'
        )
    )
```

Furthermore, you can give any object as an Executor for Prefect Flows that satisfies [the Executor interface](https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/executors/base.py) (i.e. the `submit`, `map`, and `wait` functions). In this way, the sky is the limit!
