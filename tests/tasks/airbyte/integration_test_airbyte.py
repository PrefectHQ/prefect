import unittest

from prefect.tasks.airbyte import AirbyteConnectionTask


class TestCase(unittest.TestCase):

    def test_0(self):
        task = AirbyteConnectionTask(connection_id="749c19dc-4f97-4f30-bb0f-126e53506960")
        task.run()
