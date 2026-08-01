# prefect-sandbox

`prefect-sandbox` defines a deliberately small adapter boundary for running a
command in a disposable sandbox without moving the Prefect runtime into the guest.
The first provider uses [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/)
through its `sbx` CLI.

This package is experimental. It supplies transport and lifecycle primitives, not a
Prefect task runner, worker, durable-run API, retry policy, or orchestration layer.

## Installation

Install the Python package, then install and authenticate the host-side `sbx` CLI:

```bash
pip install prefect-sandbox
brew trust docker/tap
brew install docker/tap/sbx
sbx login
sbx policy init deny-all
```

`sbx policy init` is a one-time, host-wide choice. `deny-all` is the conservative
baseline for arbitrary untrusted code. Docker recommends `balanced` for ordinary
development because it permits common package registries and AI services; choose it
only when that egress matches the workload's threat model. Follow Docker's
platform-specific prerequisites on Windows and Linux.

## Example

```python
from prefect import flow
from prefect_sandbox import SbxSandbox, sandbox_session


@flow
async def isolated_python() -> bytes:
    backend = SbxSandbox(image="python:3.12-slim")
    async with sandbox_session(backend) as sandbox:
        result = await backend.exec(
            sandbox,
            ["python", "-c", "print('hello from a sandbox')"],
            timeout=30,
        )
    if not result.ok:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout
```

Commands are argv sequences and never interpolated into a shell string. Nonzero
exit codes are returned on `SandboxResult`; provider failures raise a sandbox
exception. Captured stdout and stderr are separate byte strings and are bounded while
being read.

Providers may implement the separate `SandboxFileWriter` capability. Docker
Sandboxes does so with `sbx cp`:

```python
await backend.write_file(sandbox, "/tmp/input.bin", b"input")
```

## Security boundary

`SandboxHandle` is an opaque, process-local reference, not an authorization boundary
or authenticated token. Host-side code that can call the backend is trusted. Pass
handles only to the backend instance that returned them, use that instance from one
event loop, and do not persist handles or send them to another worker.

The only caller-controlled host data directory the adapter asks `sbx` to mount is a
newly created empty temporary workspace. It does not forward the worker's environment
to guest commands; only variables explicitly passed to `exec(..., env=...)` are
added. The selected image and Docker Sandboxes runtime still provide runtime-managed
configuration and can expose credentials configured separately through `sbx`,
including proxy-injected secrets or in-VM registry credentials. Audit that host-side
configuration as part of the deployment boundary.

This package does not configure host or organization network policy. Configure and
verify egress policy with Docker Sandboxes before running untrusted code. Destroying a
sandbox on a normal success, error, timeout, or cancellation path removes the microVM
and the temporary host directory owned by the adapter.

This first adapter layer has no durable ownership record or orphan sweeper. If the
worker process or host terminates before cleanup finishes, inspect remaining resources
with `sbx ls` and remove them with `sbx rm --force <name>`. Durable identity and
server-driven cleanup belong to the later Prefect execution concept, not this package.
