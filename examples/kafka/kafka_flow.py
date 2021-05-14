from prefect.tasks.kafka.kafka import KafkaBatchConsume, KafkaBatchProduce
from prefect import task, Flow

TOPIC = 'example_events'
BOOTSTRAP_SERVER = 'localhost:9092'
GROUP_ID = '1'


@task
def print_results(x):
	print(messages[:2])
	print(messages[-2:])
	print(len(messages))


kafka_consume = KafkaBatchConsume(BOOTSTRAP_SERVER, GROUP_ID)
kafka_produce = KafkaBatchProduce(BOOTSTRAP_SERVER)


with Flow('Kafka Example') as flow:

	messages = [{'key': str(i), 'value': str(i)} for i in range(30000)]

	kafka_produce.run(
		topic=TOPIC,
		messages=messages,
		threshold=1000,
	)

	messages = kafka_consume.run(topic=[TOPIC], timeout=1.0, message_consume_limit=10000)
	print_results(messages)


flow.run()