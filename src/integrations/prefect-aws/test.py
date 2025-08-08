import asyncio

from prefect_aws.observers.ecs import start_observer


async def main():
    await start_observer()

    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
