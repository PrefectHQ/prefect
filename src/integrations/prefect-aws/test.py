import asyncio

from prefect_aws.observers.ecs import EcsObserver, SqsSubscriber


async def main():
    sub = SqsSubscriber(queue_name="prefect-ecs-task-events", queue_region="us-east-2")
    observer = EcsObserver(sqs_subscriber=sub)
    await observer.run()


if __name__ == "__main__":
    asyncio.run(main())
