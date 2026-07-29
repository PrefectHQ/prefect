"""Run the same Prefect flow with Docker Sandboxes or Islo."""

from __future__ import annotations

import argparse

from prefect_sandbox import (
    IsloSandbox,
    SandboxBackend,
    SandboxOperation,
    SbxSandbox,
)

from prefect import flow

SOURCE = """\
import os
import platform

print(f"hello from {os.environ['SANDBOX_PROVIDER']}")
print(f"guest kernel: {platform.release()}")
"""


def backend_for(provider: str) -> SandboxBackend:
    """Build the selected backend; Islo reads `ISLO_API_KEY` from the environment."""
    if provider == "sbx":
        return SbxSandbox(image="python:3.12-slim", egress="deny")
    return IsloSandbox(egress="deny", delete_after=600)


@flow(log_prints=True)
def hello_sandbox(provider: str) -> list[str]:
    """Upload Python, run it in a disposable microVM, and return its output."""
    return SandboxOperation(
        backend_for(provider),
        ["python3 /tmp/prefect-sandbox/demo.py"],
        env={"SANDBOX_PROVIDER": provider},
        files={"/tmp/prefect-sandbox/demo.py": SOURCE},
        timeout=120,
        stream_output=False,
    ).run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("provider", choices=("sbx", "islo"))
    args = parser.parse_args()
    print("\n".join(hello_sandbox(args.provider)))
