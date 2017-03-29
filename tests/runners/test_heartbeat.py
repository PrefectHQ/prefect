import datetime
import mongoengine
import prefect.runners.heartbeat
import pytest
import time


class TestHeartbeat:

    def test_heartbeat(self):
        """
        Test that a Heartbeat updates models from its own thread.
        """

        class TestDocument(mongoengine.Document):
            fast_beat = mongoengine.fields.DateTimeField()

        model = TestDocument()
        model.save()

        heartbeat = prefect.runners.heartbeat.Heartbeat(
            model, heartbeat_interval=0.1, heartbeat_key='fast_beat')
        heartbeat.start()

        now = datetime.datetime.utcnow
        model.reload()
        # the model should have been given a heartbeat immediately
        assert (now() - model.fast_beat).total_seconds() < 0.05
        time.sleep(0.1)
        model.reload()
        # the model should just have had an updated heartbeat
        assert (now() - model.fast_beat).total_seconds() < 0.05

        heartbeat.stop()
        time.sleep(0.1)
        # the model should have no updated heartbeat
        model.reload()
        assert (now() - model.fast_beat).total_seconds() > 0.1
