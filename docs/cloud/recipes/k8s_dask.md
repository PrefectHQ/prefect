
# Dask Cluster on Kubernetes

This recipe is for a Flow deployed to Kubernetes which uses a static Dask cluster. The Dask cluster lives on the same Kubernetes cluster that the Flow runs on.

[[toc]]

### Dask YAML

`dask_scheduler.yaml` is the deployment that runs the Dask scheduler.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dask-scheduler
  labels:
    app: dask-scheduler
spec:
  replicas: 1
  selector:
    matchLabels:
      app: dask-scheduler
  template:
    metadata:
      labels:
        app: dask-scheduler
    spec:
      containers:
      - name: dask-scheduler
        image: prefecthq/prefect:latest
        args:
          - dask-scheduler
          - --port
          - '8786'
        env:
          - name: DASK_DISTRIBUTED__SCHEDULER__WORK_STEALING
            value: "False"
        ports:
          - containerPort: 8786
        resources: {}
```

`dask_worker.yaml` is the deployment that runs the Dask workers. Notice that setting `replicas: 2` means that there will be two workers in this Dask cluster.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dask-worker
  labels:
    app: dask-worker
spec:
  replicas: 2
  selector:
    matchLabels:
      app: dask-worker
  template:
    metadata:
      labels:
        app: dask-worker
    spec:
      containers:
      - image: prefecthq/prefect:latest
        args: [dask-worker, dask-scheduler:8786, --no-bokeh, --nthreads, "2", --nprocs, "2"]
        name: dask-worker
        env:
          - name: DASK_DISTRIBUTED__SCHEDULER__BLOCKED_HANDLERS
            value: "['feed', 'run_function']"
          - name: DASK_DISTRIBUTED__SCHEDULER__WORK_STEALING
            value: "False"
        resources: {}
```

`dask_service.yaml` is the service that makes the Dask scheduler accessible over `dask-scheduler:8786`.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: dask-scheduler
spec:
  selector:
    app: dask-scheduler
  ports:
  - port: 8786
    targetPort: 8786
```

:::warning Dependencies
One thing to note in this recipe is the fact that the Dask scheduler and worker pods use the base `prefecthq/prefect:latest` image. This is because our Flow has no external dependencies besides Prefect. When running Dask on Kubernetes you will want to make sure that your image contains the same dependencies as your Flow will need to execute. This could happen in ways such as using the Flow's Docker storage as the image for Dask or building a custom image with all the required dependencies.
:::

### Flow Source

`dask_flow.py` is a Flow which uses the [Remote Environment](/cloud/execution/remote_environment.html#overview) to execute a Flow on a static Dask cluster. The Dask scheduler address is the one that was assigned from `dask_service.yaml`.

```python
from prefect import task, Flow
from prefect.environments import RemoteEnvironment


@task
def get_value():
    return "Example!"


@task
def output_value(value):
    print(value)


flow = Flow(
    "Static Dask Cluster Example",
    environment=RemoteEnvironment(
        executor="prefect.engine.executors.DaskExecutor",
        executor_kwargs={
            "address": "tcp://dask-scheduler:8786"
        },
    ),
    storage=Docker(
        registry_url="gcr.io/dev/", image_name="dask-k8s-flow", image_tag="0.1.0"
    ),
)

# set task dependencies using imperative API
output_value.set_upstream(get_value, flow=flow)
output_value.bind(value=get_value, flow=flow)
```
