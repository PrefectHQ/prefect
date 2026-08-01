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
sbx policy init balanced
```

`sbx policy init` is a one-time, host-wide choice. `balanced` is Docker's
recommended development policy; choose `deny-all` or `allow-all` instead when that
better matches the host's security requirements. Follow Docker's platform-specific
prerequisites on Windows and Linux.

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

`SandboxHandle` is an opaque, trusted, process-local capability. Do not persist it,
send it to another worker, or treat it as an authenticated token.

The Docker adapter mounts only a newly created empty temporary directory. It does not
forward the worker's environment to guest commands; only variables explicitly passed
to `exec(..., env=...)` are added. The selected image and Docker Sandboxes runtime may
still provide their own environment or host-configured proxy-backed credentials.

This package does not configure host or organization network policy. Configure and
verify egress policy with Docker Sandboxes before running untrusted code. Destroying a
sandbox removes the microVM and the temporary host directory owned by the adapter.
