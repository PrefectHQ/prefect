import datetime
import mongoengine
import prefect.utilities.mongo
import pytest
import time


class TestHeartbeat:

    def test_heartbeat(self):
        """
        Test that a Heartbeat updates models from its own thread.
        """

        class TestDocument(mongoengine.Document):
            slow_beat = mongoengine.fields.DateTimeField()

        model = TestDocument()
        model.save()

        slow_beat = prefect.utilities.mongo.Heartbeat(
            model, heartbeat_interval=0.5, heartbeat_key='slow_beat')
        slow_beat.start()

        now = datetime.datetime.utcnow
        model.reload()
        assert (now() - model.slow_beat).total_seconds() < 0.1
        time.sleep(0.5)
        model.reload()
        assert (now() - model.slow_beat).total_seconds() < 0.1

        slow_beat.stop()
        time.sleep(0.5)
        assert (now() - model.slow_beat).total_seconds() > 0.5
