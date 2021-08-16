# Docker Sidecar on Kubernetes

This recipe is for a Flow deployed to Kubernetes, making use of a Docker
sidecar container to pull an image and run a container. This is an adaptation
of the [Docker Pipeline](../../core/examples/imperative_docker.md) example
where the `prefecthq/prefect:latest` image is pulled and a container is started
using that image to run another Flow inside that container.

The flow is run in a [Kubernetes
Job](https://kubernetes.io/docs/concepts/workloads/controllers/jobs-run-to-completion/)
using a custom job template. The job has two containers:

- The first will be filled in by the Kubernetes Agent to run the flow
- The second exposes a Docker daemon on `tcp://localhost:2375`

It uses a
[KubernetesRun](/orchestration/flow_config/run_configs.md#kubernetesrun) run
config to specify the custom job template. The Kubernetes Agent will use this
template when starting the flow run, instead of the default template set on the
agent.

The flow itself is composed of [Docker Tasks](/api/latest/tasks/docker.html)
from Prefect's task library. It pulls an image, starts a container, then waits
for it to finish before pulling the container's logs.

```python
from prefect import Flow
from prefect.storage import Docker
from prefect.run_configs import KubernetesRun
from prefect.tasks.docker import (
    PullImage,
    CreateContainer,
    StartContainer,
    GetContainerLogs,
    WaitOnContainer,
)
from prefect.triggers import always_run


# The custom job spec to use for this flow run.
# This contains two containers:
# - The first will be filled in by the Kubernetes Agent to run the flow
# - The second exposes a Docker daemon on `tcp://localhost:2375`
job_template = """
apiVersion: batch/v1
kind: Job
metadata:
  name: prefect-docker-job
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: flow-container
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
"""

# Initialize the tasks from the task library with all constant parameters
# Note that we pass the host of the Docker daemon to each task
image = PullImage(
    docker_server_url="tcp://localhost:2375",
    repository="prefecthq/prefect",
    tag="latest",
)
create_container = CreateContainer(
    docker_server_url="tcp://localhost:2375",
    image_name="prefecthq/prefect:latest",
    command='''python -c "from prefect import Flow; f = Flow('empty'); f.run()"''',
)
start_container = StartContainer(docker_server_url="tcp://localhost:2375")
wait_on_container = WaitOnContainer(docker_server_url="tcp://localhost:2375")
# We pass `trigger=always_run` here so the logs will always be retrieved, even
# if upstream tasks fail
get_logs = GetContainerLogs(
    docker_server_url="tcp://localhost:2375", trigger=always_run
)

with Flow("Docker sidecar example") as flow:
    # Create and start the docker container
    container_id = create_container(image)
    started = start_container(container_id=container_id)
    # Once the docker container has started, wait until it's completed and get the status
    status_code = wait_on_container(container_id=container_id, upstream_tasks=[started])
    # Once the status code has been retrieved, retrieve the logs
    logs = get_logs(container_id=container_id, upstream_tasks=[status_code])

# Configure the flow to use the custom job template
flow.run_config = KubernetesRun(job_template=job_template)
flow.storage = Docker(
    registry_url="gcr.io/dev/", image_name="docker-on-k8s-flow", image_tag="0.1.0"
)
```
