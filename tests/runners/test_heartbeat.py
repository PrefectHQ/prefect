import datetime
from prefect.models import FlowModel, FlowRunModel
import prefect.runners.heartbeat
import pytest
import time


# class TestHeartbeat:
#
#     def test_heartbeat(self):
#         """
#         Test that a Heartbeat updates models from its own thread.
#         """
#         f = prefect.flow.Flow('test')
#         f.save()
#         model = FlowRunModel.create(flow=f.id)
#
#         heartbeat = prefect.runners.heartbeat.Heartbeat(
#             model, heartbeat_interval=0.1, heartbeat_column='heartbeat')
#         heartbeat.start()
#
#         now = datetime.datetime.utcnow
#
#         model = FlowRunModel.get(FlowRunModel.id == model.id)
#         # the model should have been given a heartbeat immediately
#         assert (now() - model.heartbeat).total_seconds() < 0.05
#         time.sleep(0.1)
#         model = FlowRunModel.get(FlowRunModel.id == model.id)
#         # the model should just have had an updated heartbeat
#         assert (now() - model.heartbeat).total_seconds() < 0.05
#
#         heartbeat.stop()
#         time.sleep(0.1)
#         # the model should have no updated heartbeat
#         model = FlowRunModel.get(FlowRunModel.id == model.id)
#         assert (now() - model.heartbeat).total_seconds() > 0.1
