---
description: Learn about running integration tests for flow runners.
tags:
    - open source
    - contributing
    - development
    - testing
    - flow runners
---

# Testing flow runners

By default, Prefect's test suite does not run integration tests for flow runners
against real execution targets (like a real Docker daemon or a real Kubernetes cluster),
due to the complexity of setting them up to run locally.  You'll see this indicated with
a small `s` in the progress output of the test suite.  You'll also see a note with the
skipped tests that mentions:  "Requires service(s): 'kubernetes'. Use '--service NAME'
to include."

To enable the integration tests, you'll need to run and configure the appropriate
service locally.  Below are notes on how to test various flow runners locally.

## Testing the `DockerFlowRunner`

You'll need access to a working local Docker daemon, via [Docker
Desktop](https://www.docker.com/products/docker-desktop/) on macOS or Windows, or via
your system's package manager on Linux.

Confirm that you have a working Docker daemon with the command `docker version`.  If you
see output about both the client and server, you should be ready for testing.

### Building an image

The `DockerFlowRunner` test assumes that you have a development image of Prefect
available on the Docker daemon, and that it includes and installation of the same
version of both Python and `prefect` that you are currently testing.  You can build a
compatible image from your source tree with:

<div class="terminal">

```bash
prefect dev build-image
```

</div>

### Running the integration tests

To run the tests for the `DockerFlowRunner`, include the `--service docker` flag when
running `pytest`:

<div class="terminal">

```bash
pytest --service docker tests/flow_runners/test_docker.py
```

</div>

## Testing the `KubernetesFlowRunner`

You'll need access to a local Kubernetes cluster, and there are several great options
for running a small local cluster, including
[`minikube`](https://minikube.sigs.k8s.io/docs/start/), [Docker
Desktop](https://www.docker.com/products/docker-desktop/), and
[`microk8s`](https://microk8s.io/).

Confirm that you have a working Kubernetes cluster with `kubectl version`.  If you see
information about both a "Client Version" and  "Server Version", you should be ready
for testing.

## Building an image

As with the `DockerFlowRunner`, the `KubernetesFlowRunner` test assumes that you have an
image named `prefecthq/prefect:dev-python3.9` available on the Docker daemon, and that
it includes and installation of the same version of `prefect` that you are currently
testing.  You can build a compatible image from your source tree with:

<div class="terminal">

```bash
prefect dev build-image
```

</div>

You'll need a mechanism for making a locally-built image available to your cluster.  The
exact method differs depending on your setup.  If you are using the Kubernetes cluster
included with Docker Desktop, building the image via the `docker` command above
will be sufficient.  For other Kubernetes clusters, you may need to build to a
particular Docker daemon, or push the image to a local registry.  Consult your cluster's
documentation for more details.

## Deploying `orion` into your cluster

The steps to run `orion` for testing in your cluster's `default` namespace are:

<div class="terminal">

```bash
# Deploy orion to your cluster
prefect kubernetes manifest orion | kubectl apply -f -

# Expose port 4205 for the test suite to connect
kubectl expose service orion --type=LoadBalancer --name=orion-tests --target-port 4200 --port 4205

# wait a moment for everything to start, then create the `kubernetes` work queue for
# the orion agent sidecar so that it can feel comfortable
PREFECT_API_URL=http://localhost:4205/api prefect work-queue create kubernetes
```

</div>

The example above creates a `LoadBalancer` Kubernetes `Service` on your cluster to
expose the Orion API on `http://localhost:4205/api`, which you may use as your
`PREFECT_API_URL` for interacting with that service.

You may also use port-forwarding if you are connecting to a remote cluster, or have
other use cases where a load-balancer service won't work for your situation.  You can
accomplish that with:

<div class="terminal">

```bash
kubectl port-forward deployment/orion 4205:4200
```

</div>

Keep in mind that for the `KubernetesFlowRunner` integration tests to succeed, the
cluster must have access to mount the local `.prefect-results` directory to
`/tmp/prefect` in order to confirm that the example flow run completed successfully.

If you need to customize the deployment or run it in a different namespace, you can
output the manifest to a file, edit what you need, and apply it:

<div class="terminal">

```bash
prefect kubernetes manifest orion > orion.yaml
# ... edit orion.yaml ...
kubectl apply -f orion.yaml
```


</div>

### Running the integration tests

To run the tests for the `KubernetesFlowRunner`, include the `--service kubernetes` flag
when running `pytest`:

<div class="terminal">

```bash
pytest --service kubernetes tests/flow_runners/test_docker.py
```

</div>
