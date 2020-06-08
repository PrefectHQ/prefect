# Docker Sidecar on Kubernetes <Badge text="Cloud"/>

This recipe is for a Flow deployed to Kubernetes, making use of a Docker sidecar container to pull an image and run a container. This is an adaptation of the [Docker Pipeline](../../core/examples/imperative_docker.html) example where the `prefecthq/prefect:latest` image is pulled and a container is started using that image to run another Flow inside that container.

[[toc]]

### Job Spec YAML

`job_spec.yaml` is going to be the custom [Job](https://kubernetes.io/docs/concepts/workloads/controllers/jobs-run-to-completion/) YAML that will be passed into the Flow's [Kubernetes Job Environment](/orchestration/execution/k8s_job_environment.html). We have two containers for this Job: The Kubernetes Job Environment will use the first container to run the Flow; the second container will have an accessible Docker daemon over `tcp://localhost:2375`.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: prefect-docker-job
  labels:
    identifier: ''
spec:
  template:
    metadata:
      labels:
        identifier: ''
    spec:
      restartPolicy: Never
      containers:
        - name: flow-container
          image: ''
          command: []
          args: []
          env:
            - name: DOCKER_HOST
              value: tcp://localhost:2375
        - name: dind-daemon
          image: docker:stable-dind
          env:
            - name: DOCKER_TLS_CERTDIR
              value: ""
          resources:
            requests:
              cpu: 20m
              memory: 512Mi
          securityContext:
            privileged: true
          volumeMounts:
            - name: docker-graph-store
              mountPath: /var/lib/docker
      volumes:
        - name: docker-graph-store
          emptyDir: {}
```

### Flow Source

`k8s_docker.py` is a Flow which uses the Kubernetes Job Environment to create a custom Job that has access to the Docker sidecar in order to use the [Docker Tasks](/core/task_library/docker.html) found in the [Prefect Task Library](/core/task_library/).

```python
from prefect import Flow
from prefect.environments import KubernetesJobEnvironment
from prefect.environments.storage import Docker
from prefect.tasks.docker import (
    PullImage,
    CreateContainer,
    StartContainer,
    GetContainerLogs,
    WaitOnContainer,
)
from prefect.triggers import always_run


# Pass the host of the Docker daemon to each task
image = PullImage(
    docker_server_url="tcp://localhost:2375",
    repository="prefecthq/prefect",
    tag="latest",)
container = CreateContainer(
    docker_server_url="tcp://localhost:2375",
    image_name="prefecthq/prefect:latest",
    command='''python -c "from prefect import Flow; f = Flow('empty'); f.run()"''',
)
start = StartContainer(docker_server_url="tcp://localhost:2375",)
logs = GetContainerLogs(docker_server_url="tcp://localhost:2375", trigger=always_run)
status_code = WaitOnContainer(docker_server_url="tcp://localhost:2375",)

flow = Flow(
    "Run a Prefect Flow in Docker",
    environment=KubernetesJobEnvironment(job_spec_file="job_spec.yaml"),
    storage=Docker(
        registry_url="gcr.io/dev/", image_name="docker-on-k8s-flow", image_tag="0.1.0"
    ),
)

# set task dependencies using imperative API
container.set_upstream(image, flow=flow)
start.set_upstream(container, flow=flow, key="container_id")
logs.set_upstream(container, flow=flow, key="container_id")
status_code.set_upstream(container, flow=flow, key="container_id")

status_code.set_upstream(start, flow=flow)
logs.set_upstream(status_code, flow=flow)
```
