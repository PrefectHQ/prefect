from confluent_kafka import Consumer, Producer, KafkaError, KafkaException
from typing import List
from prefect import Task


class KafkaBatchConsume(Task):
    """
    Task for consuming a batch messages from a Kafka topic.
    """

    def __init__(self, bootstrap_servers: str, group_id: str, **kwargs):

        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id

        super().__init__(**kwargs)

    def run(
        self,
        topic: str,
        timeout: float = 1.0,
        auto_offset_reset: str = 'earliest',
        message_consume_limit: int = None,
        **consumer_options,
    ) -> List[bytes]:
        consumer = Consumer(
            {
                'bootstrap.servers': self.bootstrap_servers,
                'group.id': self.group_id,
                'auto.offset.reset': auto_offset_reset,
                **consumer_options,
            }
        )
        consumer.subscribe(topic)

        messages = []
        message_consume_count = 0
        running = True

        try:
            while running:
                message = consumer.poll(timeout=timeout)

                if message is not None:
                    if message.error():
                        if mesage.error().code() == KafkaError._PARTITION_EOF:
                            # End of partition event, exit consumer
                            self.logger.warn(
                                f"{msg.topic()} [{msg.partition()}] reached end at offset {msg.offset()}"
                            )
                            running = False
                        elif message.error():
                            raise KafkaException(message.error())
                    else:
                        messages.append(message.value())
                        message_consume_count += 1

                        if message_consume_limit:
                            if message_consume_count >= message_consume_limit:
                                break
                else:
                    self.logger.debug(
                        f"No messages found for topic {topic}; closing consumer..."
                    )
                    break

        finally:
            consumer.close()

        return messages


class KafkaBatchProduce(Task):
    """
    Task for producing a batch of messages to Kafka topic
    """

    def __init__(self, bootstrap_servers: str, **kwargs):
        self.bootstrap_servers = bootstrap_servers
        super().__init__(**kwargs)

    def run(
        self,
        topic: str,
        messages: List[dict],
        threshold: int = None,
        callback=None,
        **producer_options,
    ):

        producer = Producer(
            {'bootstrap.servers': self.bootstrap_servers, **producer_options}
        )
        message_produce_count = 0

        for i, message in enumerate(messages):
            if threshold:
                if i % threshold == 0:
                    producer.flush()
                    self.logging.debug(
                        f"Producer flushed {threshold} messages to {topic}"
                    )

            key = message.get('key')
            value = message.get('value')

            producer.produce(topic=topic, key=key, value=value, callback=callback)
            message_produce_count += 1

        producer.flush()
        self.logging.debug(
            f"Producer flushed {message_produce_count} messages to {topic}"
        )
