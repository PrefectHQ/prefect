# prefect-armada integration tests

End-to-end tests that run flow runs as Armada jobs: a real Prefect API, a real
`prefect worker`, and a real Armada cluster.

## Prerequisites

- A [kind](https://kind.sigs.k8s.io/) cluster running Armada. The
  [armada-operator](https://github.com/armadaproject/armada-operator/) creates
  one, named `armada`, with `make kind-all`. The tests do not create the
  cluster, because Armada has to be deployed on top of it.
- Docker, `kind`, and `uv` on your `PATH`.
- A Prefect server that flow-run pods can reach, which means it must listen on
  more than the loopback interface:

  ```bash
  prefect server start --host 0.0.0.0
  ```

**Note**: a Prefect worker pool does _not_ need to be started before running the
tests - the test suite will create and start the worker pool, and will terminate
it when the test suite finishes.

## Running the tests

Point the tests at the Prefect API and the Armada server, then run `pytest` from
this directory:

```bash
export PREFECT_API_URL=http://127.0.0.1:4200/api
export PREFECT_INTEGRATIONS_ARMADA_CONNECTION_HOST=localhost
export PREFECT_INTEGRATIONS_ARMADA_CONNECTION_PORT=30002
# For a cluster serving plaintext gRPC, which is how armada-operator sets it up:
export PREFECT_INTEGRATIONS_ARMADA_CONNECTION_DISABLE_SSL=true
# For a cluster serving TLS with a privately-issued certificate instead:
# export PREFECT_INTEGRATIONS_ARMADA_CONNECTION_ROOT_CERTIFICATES_PATH=/path/to/ca.crt

uv run pytest -s
```

The workers the tests start inherit this environment, so they connect to Armada
the same way the tests do.

The tests take care of the rest of the setup:

- **Flow code.** The flows in `src/prefect_armada_integration_tests/image/` are
  built into an image and loaded into the kind cluster's nodes, so pods need
  neither a registry nor a git checkout.
- **Armada queue.** Flow runs are submitted to the worker's default queue
  (`prefect`, or `PREFECT_INTEGRATIONS_ARMADA_WORKER_DEFAULT_QUEUE`), which is
  created if it does not exist. It is not deleted afterwards.
- **Work pool.** A work pool with a generated name (`armada-test-<suffix>`) is
  created and deleted again when the session ends. The tests never overwrite or
  delete a work pool they did not create: if `--work-pool-name` names a pool
  that already exists, they stop before changing anything.
- **Reaching the Prefect API from pods.** The gateway of the `kind` Docker
  network is passed to flow runs as the `api_dns_name` job variable.

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--kind-cluster-name` | `armada` | Name of the kind cluster running Armada. |
| `--work-pool-name` | `armada-test-<suffix>` | Name of the work pool to create and use. Must not already exist. |
| `--api-dns-name` | kind network gateway | Address the Prefect API is reachable at from inside the cluster. |
