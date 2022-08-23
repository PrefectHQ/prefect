from typing import List, Callable

import confluent_kafka
from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class KafkaBatchConsume(Task):
    """
    Task for consuming a batch of messages from Kafka topics.

    Args:
        - bootstrap_servers (str, optional): comma separated host and port pairs that are the
            addresses of kafka brokers.
        - group_id (str, required): name of the consumer group the consumer will belong to.
            Must be specified either at init or runtime.
        - topics (List[str], required): list of topic names to consume messages from. Must
            be specified either at init or runtime.
        - request_timeout (float, optional): Maximum time to block waiting for message, event or callback
        - auto_offset_reset (str, optional): configurable offset reset policy
        - message_consume_limit (int, optional): max number of messages to consume before closing
            the consumer
        - kafka_configs (dict, optional): a dict of kafka client configuration properties used to
            construct the consumer.
        - **kwargs (Any, optional): additional keyword arguments to pass to the standard Task
            init method
    """

    def __init__(
        self,
        bootstrap_servers: str = None,
        group_id: str = None,
        topics: List[str] = None,
        request_timeout: float = 1.0,
        auto_offset_reset: str = "earliest",
        message_consume_limit: int = None,
        kafka_configs: dict = None,
        **kwargs,
    ):

        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.topics = topics
        self.request_timeout = request_timeout
        self.auto_offset_reset = auto_offset_reset
        self.message_consume_limit = message_consume_limit
        self.kafka_configs = kafka_configs or {}
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "bootstrap_servers",
        "group_id",
        "topics",
        "request_timeout",
        "auto_offset_reset",
        "message_consume_limit",
        "kafka_configs",
    )
    def run(
        self,
        bootstrap_servers: str = None,
        group_id: str = None,
        topics: List[str] = None,
        request_timeout: float = 1.0,
        auto_offset_reset: str = "earliest",
        message_consume_limit: int = None,
        kafka_configs: dict = None,
        **kwargs,
    ) -> List[bytes]:
        """
        Run method for this Task. Invoked by calling this Task after initialization within a
        Flow context, or by using `Task.bind`.
        Args:
            - bootstrap_servers (str, required): comma separated host and port pairs that are the
                addresses of kafka brokers
            - group_id (str, required): name of the consumer group the consumer will belong to
            - topics (List[str], required): list of topic names to consume messages from
            - request_timeout (float, optional): Maximum time to block waiting for message, event
                or callback
            - auto_offset_reset (str, optional): configurable offset reset policy
            - message_consume_limit (int, optional): max number of messages to consume before
                closing the consumer
            - kafka_configs (dict, optional): a dict of kafka client configuration properties used
                to construct the consumer.
            - **kwargs (Any, optional): additional keyword arguments to pass to the standard Task
                init method
        Returns:
            - List of consumed messages
        """
        consumer = confluent_kafka.Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": group_id,
                "auto.offset.reset": auto_offset_reset,
                **kafka_configs,
            }
        )
        consumer.subscribe(topics)

        messages = []
        message_consume_count = 0
        running = True

        try:
            while running:
                message = consumer.poll(timeout=request_timeout)

                if message is not None:
                    if message.error():
                        if (
                            message.error().code()
                            == confluent_kafka.KafkaError._PARTITION_EOF
                        ):
                            # End of partition event, exit consumer
                            self.logger.warning(
                                f"{message.topic()} [{message.partition()}] "
                                f"reached end at offset {message.offset()}"
                            )
                            running = False
                        elif message.error():
                            raise confluent_kafka.KafkaException(message.error())
                    else:
                        messages.append(message.value())
                        message_consume_count += 1

                        if message_consume_limit:
                            if message_consume_count >= message_consume_limit:
                                break
                else:
                    self.logger.info(
                        f"No messages found for topic {topics}; closing consumer..."
                    )
                    break

        finally:
            consumer.close()

        return messages


class KafkaBatchProduce(Task):
    """
    Task for producing a batch of messages to a Kafka topic.

    Args:
        - bootstrap_servers (str, required): comma separated host and port pairs that are the
            addresses of kafka brokers
        - topic (str, required): name of topic to produce messages to. Must be specified
            either at init or runtime.
        - messages (List[dict], required): list of messages to produce into a topic where
            a single message is a dictionary with a key and a value.
        - flush_threshold (int, optional): threshold of messages produced before flushing
        - callback (Callable, optional): callback assigned to a produce call
        - kafka_configs (dict, optional): a dict of kafka client configuration properties used to
            construct the producer.
        - **kwargs (Any, optional): additional keyword arguments to pass to the standard Task
            init method
    """

    def __init__(
        self,
        bootstrap_servers: str = None,
        topic: str = None,
        messages: List[dict] = None,
        flush_threshold: int = None,
        callback: Callable = None,
        kafka_configs: dict = None,
        **kwargs,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.messages = messages
        self.flush_threshold = flush_threshold
        self.callback = callback
        self.kafka_configs = kafka_configs or {}
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "bootstrap_servers",
        "topic",
        "messages",
        "flush_threshold",
        "callback",
        "kafka_configs",
    )
    def run(
        self,
        bootstrap_servers: str = None,
        topic: str = None,
        messages: List[dict] = None,
        flush_threshold: int = None,
        callback: Callable = None,
        kafka_configs: dict = None,
    ):
        """
        Run method for this Task. Invoked by calling this Task after initialization within a
        Flow context, or by using `Task.bind`.
        Args:
        - bootstrap_servers (str, required): comma separated host and port pairs that are the
            addresses of kafka brokers
        - topic (str, required): name of topics to produce messages to
        - messages (List[dict], required): list of messages to produce into topics where
            a single message is a dictionary with a key and a value.
        - flush_threshold (int, optional): threshold of messages produced before flushing
        - callback (Callable, optional): callback assigned to a produce call
        - kafka_configs (dict, optional): a dict of kafka client configuration properties used to
            construct the producer.
        """

        producer = confluent_kafka.Producer(
            {"bootstrap.servers": bootstrap_servers, **kafka_configs}
        )
        message_produce_count = 0

        for i, message in enumerate(messages):
            if flush_threshold:
                if i % flush_threshold == 0:
                    producer.flush()
                    self.logger.info(
                        f"Producer flushed {flush_threshold} messages to {topic}"
                    )
                    message_produce_count = 0

            key = message.get("key")
            value = message.get("value")

            producer.produce(topic=topic, key=key, value=value, callback=callback)
            message_produce_count += 1

        producer.flush()
        self.logger.info(
            f"Producer flushed {message_produce_count} messages to {topic}"
        )
