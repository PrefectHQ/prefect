import pytest
from unittest import mock
from prefect.tasks.kafka.kafka import KafkaBatchConsume, KafkaBatchProduce


class TestKafkaBatchConsume:
    def test_construction(self):
        task = KafkaBatchConsume('localhost:9092', '1')
        assert task.bootstrap_servers == 'localhost:9092'
        assert task.group_id == '1'

        # raises when group_id isn't provided
        with pytest.raises(TypeError):
            task = KafkaBatchConsume('localhost:9092')

    def test_topic_must_be_provided(self):
        task = KafkaBatchConsume('localhost:9092', '1')
        with pytest.raises(TypeError):
            task.run()

    def test_no_messages_received(self):
        task = KafkaBatchConsume('localhost:9092', '1')
        assert task.run(['topic']) == []

    @mock.patch("prefect.tasks.kafka.kafka.confluent_kafka")
    def test_consumer_finally_closes(self, mock_confluent_kafka):
        mock_consumer = mock.MagicMock()
        mock_confluent_kafka.Consumer.return_value = mock_consumer
        mock_consumer.poll.return_value = None
        task = KafkaBatchConsume('localhost:9092', '1')
        task.run(['topic'])
        assert mock_consumer.close.called

    @mock.patch("prefect.tasks.kafka.kafka.confluent_kafka")
    def test_consumer_consumes_until_no_messages(self, mock_confluent_kafka):
        mock_consumer = mock.MagicMock()
        mock_message = mock.MagicMock()
        mock_message.value.return_value = 'value'
        mock_message.error.return_value = None
        mock_confluent_kafka.Consumer.return_value = mock_consumer
        mock_consumer.poll.side_effect = [mock_message, mock_message, None]
        task = KafkaBatchConsume('localhost:9092', '1')
        messages = task.run(['topic'])
        assert len(messages) == 2
        for message in messages:
            assert message == 'value'
