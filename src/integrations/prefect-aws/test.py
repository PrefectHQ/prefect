import asyncio
from typing import Any

from prefect_aws.observers.ecs import EcsObserver, FilterCase, SqsSubscriber


async def main():
    sub = SqsSubscriber(queue_name="prefect-ecs-task-events", queue_region="us-east-2")
    observer = EcsObserver(sqs_subscriber=sub)

    @observer.on_event("task", tags={"prefect.io/flow-run-id": FilterCase.PRESENT})
    def on_task_event(event: dict[str, Any], tags: dict[str, str]):
        print(f"Received task event with tags: {tags}")

    await observer.run()


if __name__ == "__main__":
    asyncio.run(main())
