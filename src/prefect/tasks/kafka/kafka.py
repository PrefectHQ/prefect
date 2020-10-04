from confluent_kafka import Consumer
from typing import List

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class KafkaConsume(Task):
    """
    Tasks for consuming kafka messages from a topic.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        **kwargs,
    ):

    self.bootstrap_servers = bootstrap_servers
    self.group_id = group_id

    super().__init__(**kwargs)


    def run(self, topic: str, timeout: float = None):
        consumer = Consumer(
            {
                'bootstrap.servers': self.bootstrap_servers,
                'group_id': self.group_id,
            }
        )
        consumer.subscribe(topic)

        messages = []
        running = True

        try:
            while running:
                message = consumer.poll(timeout=timeout)
                if message:
                    if not message.error():
                        messages.append(message.value())
                    elif: message.error().code() != KafkaError._PARTITION_EOF:
                        running = False
        finally:
            consumer.close()

        return messages
