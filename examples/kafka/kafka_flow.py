import time
from prefect.tasks.kafka.kafka import KafkaBatchConsume, KafkaBatchProduce
from prefect import task, Flow, Parameter

TOPIC = "example_events"
BOOTSTRAP_SERVER = "localhost:9092"
GROUP_ID = "1"


@task
def print_results(x):
    print(f"First two messages: {x[:2]}")
    print(f"Last two messages: {x[-2:]}")
    print(f"Total messages: {len(x)}")


with Flow("Kafka Example") as flow:
    messages = [{"key": str(i), "value": str(i)} for i in range(30000)]

    produce_20k = KafkaBatchProduce(
        bootstrap_servers=BOOTSTRAP_SERVER,
        topic=TOPIC,
        messages=messages[0:20000],
        flush_threshold=1000,
    )

    produce_remaining = KafkaBatchProduce(
        bootstrap_servers=BOOTSTRAP_SERVER,
        topic=TOPIC,
        messages=messages[20000:],
        flush_threshold=1000,
    )

    consume_10k = KafkaBatchConsume(
        bootstrap_servers=BOOTSTRAP_SERVER,
        group_id=GROUP_ID,
        topics=[TOPIC],
        request_timeout=1.0,
        message_consume_limit=10000,
        auto_offset_reset="latest",
    )

    consume_remaining = KafkaBatchConsume(
        bootstrap_servers=BOOTSTRAP_SERVER,
        group_id=GROUP_ID,
        topics=[TOPIC],
        request_timeout=1.0,
    )

    produce_20k.set_downstream(
        task=consume_10k.set_downstream(task=print_results, key="x")
    )

    produce_remaining.set_downstream(
        task=consume_remaining.set_downstream(task=print_results, key="x")
    )

flow.run()
