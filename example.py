from prefect.runner import Runner, GitSynchronizer
import asyncio


async def main():
    runner = Runner()
    await runner.add_synchronizer(
        GitSynchronizer(repository="https://github.com/desertaxle/demo.git")
    )
    await runner.add_flow_from_entrypoint(
        entrypoint="flow.py:my_flow", name="test-remote-sync"
    )
    await runner.start()


if __name__ == "__main__":
    asyncio.run(main())
