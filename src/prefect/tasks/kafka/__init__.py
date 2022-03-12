"""
This module contains a collection of tasks to produce and consume Kafka events
"""

try:
    from prefect.tasks.kafka.kafka import KafkaBatchConsume, KafkaBatchProduce
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.kafka` requires Prefect to be installed with the "kafka" extra.'
    ) from err

__all__ = ["KafkaBatchConsume", "KafkaBatchProduce"]
