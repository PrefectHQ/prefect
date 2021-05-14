import time
from prefect.tasks.kafka.kafka import KafkaBatchConsume, KafkaBatchProduce
from prefect import task, Flow

TOPIC = 'example_events'
BOOTSTRAP_SERVER = 'localhost:9092'
GROUP_ID = '1'


@task
def print_results(x):
    print(f'First two messages: {x[:2]}')
    print(f'Last two messages: {x[-2:]}')
    print(f'Total messages: {len(x)}')


kafka_consume = KafkaBatchConsume(BOOTSTRAP_SERVER, GROUP_ID)
kafka_produce = KafkaBatchProduce(BOOTSTRAP_SERVER)


with Flow('Kafka Example') as flow:

    messages = [{'key': str(i), 'value': str(i)} for i in range(30000)]

    kafka_produce.run(
        topic=TOPIC,
        messages=messages,
        threshold=1000,
    )

    time.sleep(5)

    messages = kafka_consume.run(topic=[TOPIC], timeout=1.0, message_consume_limit=10000)
    print_results(messages)

    remaining_messages = kafka_consume.run(topic=[TOPIC], timeout=1.0)
    print_results(remaining_messages)

flow.run()
