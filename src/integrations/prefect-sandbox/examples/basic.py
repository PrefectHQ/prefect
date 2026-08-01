"""Run one command in a disposable Docker Sandbox."""

import asyncio

from prefect_sandbox import SbxSandbox, sandbox_session


async def main() -> None:
    backend = SbxSandbox(image="python:3.12-slim")
    async with sandbox_session(backend) as sandbox:
        result = await backend.exec(
            sandbox,
            ["python", "-c", "print('hello from a sandbox')"],
            timeout=30,
        )
    print(result.stdout.decode(errors="replace"), end="")


if __name__ == "__main__":
    asyncio.run(main())
