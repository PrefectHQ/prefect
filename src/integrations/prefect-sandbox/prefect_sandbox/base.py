"""Vendor-neutral contract for running commands inside an isolated sandbox.

A *sandbox* here is not a container. It is an ephemeral, kernel-isolated environment
that is created for a piece of work and destroyed afterwards, and that inherits none
of the calling worker's credentials. That trust model — code you did not author — is
what separates this from `prefect-docker`, and it is what every rule in this module
is protecting.

Implementations live in sibling modules or in third-party packages; see the
prefect-sandbox integration documentation for the onboarding contract.
"""

from __future__ import annotations

import asyncio
import base64
import shlex
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import ClassVar

from pydantic import Field

from prefect.blocks.core import Block

__all__ = [
    "DEFAULT_MAX_OUTPUT_BYTES",
    "SANDBOX_NAME_PREFIX",
    "Sandbox",
    "SandboxBackend",
    "SandboxCreationError",
    "SandboxError",
    "SandboxExecutionError",
    "SandboxResult",
    "SandboxUnavailableError",
    "new_sandbox_name",
    "validate_env",
]

#: Default per-stream cap on captured output. Sandboxed code is frequently
#: model-generated and can print without bound; a cap keeps a runaway command from
#: growing the worker's resident memory and from flooding the Prefect API with logs.
DEFAULT_MAX_OUTPUT_BYTES = 64 * 1024

#: Prefix for generated sandbox names, so orphans are identifiable on the host or in
#: a vendor console and can be swept up by name.
SANDBOX_NAME_PREFIX = "prefect-sandbox-"

#: Ceiling on content written through the portable `awrite_file` fallback, which
#: smuggles the payload through the command line. Backends with a native file API
#: should override `awrite_file` and are not bound by this.
MAX_INLINE_FILE_BYTES = 256 * 1024


class SandboxError(Exception):
    """Base class for every sandbox failure."""


class SandboxUnavailableError(SandboxError):
    """The backend cannot be used at all: missing binary, missing SDK, or no credentials.

    Raised instead of a bare `ImportError`/`FileNotFoundError` so callers can tell
    "this backend is not installed here" apart from "this command failed".
    """


class SandboxCreationError(SandboxError):
    """A sandbox could not be provisioned."""


class SandboxExecutionError(SandboxError):
    """Infrastructure failed while running a command.

    A *nonzero exit code is not an error* — that is data, returned on
    `SandboxResult`. This is for the case where the sandbox itself broke.
    """


@dataclass(frozen=True)
class Sandbox:
    """A handle to one provisioned sandbox.

    Deliberately self-contained: everything a backend needs in order to exec into
    this sandbox and later tear it down travels in `metadata`, rather than in a dict
    on the backend instance. A backend therefore holds no per-sandbox mutable state,
    which is what makes a single shared backend instance safe for concurrent flow
    runs — two runs cannot see, overwrite, or destroy each other's sandbox.
    """

    id: str
    backend: str
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.backend}:{self.id}"


@dataclass(frozen=True)
class SandboxResult:
    """The outcome of one command execution inside a sandbox.

    Attributes:
        exit_code: The command's exit status. Meaningless when `timed_out` is set.
        stdout: Captured standard output, capped at the backend's `max_output_bytes`.
        stderr: Captured standard error, capped the same way.
        timed_out: True only when the timeout genuinely fired. Never inferred from
            elapsed wall-clock time.
        truncated: True when either stream hit the cap.
        sandbox_terminated: True when the backend had to destroy the sandbox in order
            to stop the command. The handle is dead; provision a new one.
    """

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    truncated: bool = False
    sandbox_terminated: bool = False

    @property
    def ok(self) -> bool:
        """True when the command completed successfully."""
        return self.exit_code == 0 and not self.timed_out

    def raise_for_status(self) -> None:
        """Raise `SandboxExecutionError` unless the command succeeded."""
        if self.ok:
            return
        if self.timed_out:
            raise SandboxExecutionError(
                f"Command timed out in sandbox{' (sandbox destroyed)' if self.sandbox_terminated else ''}."
            )
        detail = (self.stderr or self.stdout or "").strip()
        raise SandboxExecutionError(
            f"Command failed in sandbox with exit code {self.exit_code}."
            + (f" Output: {detail[-2000:]}" if detail else "")
        )


def new_sandbox_name() -> str:
    """Generate a unique, identifiable sandbox name."""
    return f"{SANDBOX_NAME_PREFIX}{uuid.uuid4().hex[:12]}"


def validate_env(env: Mapping[str, str] | None) -> None:
    """Reject environment variables a POSIX `env` invocation cannot express."""
    for key, value in (env or {}).items():
        if not key or "=" in key or "\0" in key:
            raise ValueError(f"Invalid environment variable name: {key!r}")
        if "\0" in str(value):
            raise ValueError(f"Environment variable {key!r} contains a null byte.")


async def _shielded_cleanup(awaitable: Awaitable[None]) -> None:
    """Finish cleanup before delivering cancellation to the caller."""
    cleanup = asyncio.ensure_future(awaitable)
    cancelled = False
    while not cleanup.done():
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            cancelled = True
    cleanup.result()
    if cancelled:
        raise asyncio.CancelledError


class SandboxBackend(Block, ABC):
    """Contract for provisioning sandboxes and running commands inside them.

    The lifecycle is `acreate` → `aexec` (any number of times) → `adestroy`.

    Implementations must honour these invariants:

    1. **Stateless with respect to handles.** All per-sandbox state travels in
       `Sandbox.metadata`. One backend instance shared by concurrent flow runs must
       never let one run observe or destroy another's sandbox.
    2. **Cheap construction.** `__init__` performs no I/O and resolves no
       credentials — Block instances are built at import time. Resolve lazily.
    3. **`adestroy` is idempotent.** Destroying an already-gone sandbox succeeds.
    4. **A failed `acreate` leaks nothing** — no half-provisioned sandbox, no host
       temp state.
    5. **Output is capped while streaming**, never buffered in full and truncated
       afterwards, and `truncated` is set when the cap bites.
    6. **Timeouts are honest.** Set `timed_out` only when the timeout actually
       fired, and `sandbox_terminated` when stopping the command cost the sandbox.
    7. **No ambient credentials.** Nothing from the worker environment — above all
       `PREFECT_API_KEY` — reaches the sandbox unless the caller passed it in `env`.
    8. **A nonzero exit is not an exception.** Return it on `SandboxResult`; raise
       only for genuine infrastructure failure.

    Concrete subclasses are ordinary Prefect Blocks, so a configured backend can be
    saved and reused by name:

    ```python
    from prefect_sandbox import SbxSandbox

    SbxSandbox(image="python:3.12-slim", memory="4g").save("scratch")
    ```
    """

    _block_schema_capabilities: ClassVar[list[str]] = ["run-in-sandbox"]

    #: Short identifier recorded on every `Sandbox` this backend creates.
    backend_name: ClassVar[str]

    max_output_bytes: int = Field(
        default=DEFAULT_MAX_OUTPUT_BYTES,
        gt=0,
        title="Max Output Bytes",
        description=(
            "Maximum bytes of stdout and of stderr to capture from each command. "
            "Output beyond this is discarded and the result is flagged as truncated."
        ),
    )

    @abstractmethod
    async def acreate(self) -> Sandbox:
        """Provision one sandbox and return its handle."""

    @abstractmethod
    async def aexec(
        self,
        sandbox: Sandbox,
        command: Sequence[str],
        *,
        timeout: float,
        env: Mapping[str, str] | None = None,
        working_dir: str | None = None,
    ) -> SandboxResult:
        """Run `command` (an argv list, no shell) inside `sandbox`.

        Args:
            sandbox: Handle returned by `acreate`.
            command: Argv to execute. Not passed through a shell, so the caller does
                not need to quote anything.
            timeout: Seconds the command may run before it is stopped.
            env: Environment variables to set for this command only.
            working_dir: Directory to run in.

        Returns:
            A `SandboxResult`. A nonzero exit code is reported here, not raised.
        """

    @abstractmethod
    async def adestroy(self, sandbox: Sandbox) -> None:
        """Tear down `sandbox`. Idempotent."""

    async def aclose(self) -> None:
        """Release backend-level resources such as HTTP connections.

        Separate from `adestroy`, which disposes of a single sandbox. The default is
        a no-op; backends holding a client should override it.
        """

    async def awrite_file(self, sandbox: Sandbox, path: str, content: str) -> None:
        """Write `content` to `path` inside `sandbox`.

        The default implementation needs nothing but `aexec`: it base64-encodes the
        payload and decodes it inside the sandbox, which keeps arbitrary bytes and
        quoting hazards out of the command line. Backends with a native file-transfer
        API should override this — the fallback is bounded by
        `MAX_INLINE_FILE_BYTES` because the payload rides on the command line.
        """
        raw = content.encode()
        if len(raw) > MAX_INLINE_FILE_BYTES:
            raise SandboxError(
                f"{len(raw)} bytes exceeds the {MAX_INLINE_FILE_BYTES}-byte limit for "
                f"inline file writes. {type(self).__name__} has no native file "
                "transfer; write the data in chunks or use a backend that does."
            )
        encoded = base64.b64encode(raw).decode()
        directory = path.rsplit("/", 1)[0] if "/" in path else ""
        script = (
            f"mkdir -p {shlex.quote(directory)} && " if directory else ""
        ) + f"printf %s {shlex.quote(encoded)} | base64 -d > {shlex.quote(path)}"
        result = await self.aexec(sandbox, ["sh", "-c", script], timeout=60)
        if not result.ok:
            raise SandboxError(
                f"Failed to write {path!r} into {sandbox}: "
                f"exit {result.exit_code} {result.stderr.strip()[:500]}"
            )

    @asynccontextmanager
    async def asession(self) -> AsyncIterator[Sandbox]:
        """Provision a sandbox for the duration of the block and always destroy it.

        ```python
        async with backend.asession() as sandbox:
            result = await backend.aexec(sandbox, ["python", "-c", "print(1)"], timeout=30)
        ```
        """
        sandbox = await self.acreate()
        try:
            yield sandbox
        finally:
            await _shielded_cleanup(self.adestroy(sandbox))
