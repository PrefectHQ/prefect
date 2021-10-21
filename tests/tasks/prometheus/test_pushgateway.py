from unittest.mock import MagicMock
import prometheus_client
import prometheus_client.exposition
import pytest
from prefect.tasks.prometheus.pushgateway import (
    PushAddGaugeToGateway,
    PushGaugeToGateway,
    _GaugeToGatewayBase,
)


@pytest.fixture
def use_gateway_mock(monkeypatch):
    pushaddgateway = MagicMock()
    monkeypatch.setattr(
        prometheus_client.exposition,
        "_use_gateway",
        pushaddgateway,
    )
    return pushaddgateway


@pytest.fixture
def push_mock(monkeypatch):
    push = MagicMock()
    monkeypatch.setattr(
        _GaugeToGatewayBase,
        "_push",
        push,
    )
    return push


class TestGaugeToGatewayBase:
    def test_can_instanciate_PushGaugeToGateway(self):
        task = _GaugeToGatewayBase()
        assert task is not None

    def test_can_initialize_pushgateway_url(self):
        url = "http://pushgateway.com"
        task = _GaugeToGatewayBase(pushgateway_url=url)
        assert task.pushgateway_url == url

    def test_can_initialize_counter_name(self):
        counter_name = "requests-per-second"
        task = _GaugeToGatewayBase(counter_name=counter_name)
        assert task.counter_name == counter_name

    def test_can_initialize_counter_description(self):
        counter_description = "Number of request per second"
        task = _GaugeToGatewayBase(counter_description=counter_description)
        assert task.counter_description == counter_description

    def test_can_initialize_job_name(self):
        job_name = "my-job"
        task = _GaugeToGatewayBase(job_name=job_name)
        assert task.job_name == job_name

    def test_can_initialize_with_kwarg(self):
        task = _GaugeToGatewayBase(name="My push gateway")
        assert task.name == "My push gateway"

    def test_raise_exception_when_url_missing(self):
        task = _GaugeToGatewayBase(name="My push gateway")
        with pytest.raises(ValueError) as ex:
            task.run(labels=[], values=[])
            assert "pushgateway_url" in str(ex.value)

    def test_raise_exception_when_conter_name_missing(self):
        url = "http://pushgateway.com"
        task = _GaugeToGatewayBase(pushgateway_url=url)
        with pytest.raises(ValueError) as ex:
            task.run(labels=[], values=[])
            assert "counter_name" in str(ex.value)

    def test_raise_exception_when_len_value_diff_label(self):
        url = "http://pushgateway.com"
        counter_name = "flow_grid_rows"
        task = _GaugeToGatewayBase(pushgateway_url=url, counter_name=counter_name)
        with pytest.raises(ValueError) as ex:
            task.run(values=[1], labels=[])
            assert "Values and labels" in str(ex.value)

    def test_empty_value_no_call_push_gateway(
        self, push_gateway_mock, pushadd_gateway_mock
    ):
        url = "http://pushgateway.com"
        counter_name = "flow_grid_rows"
        task = _GaugeToGatewayBase(pushgateway_url=url, counter_name=counter_name)
        task.run(values=[], labels=[])
        assert push_gateway_mock.call_count == 0
        assert pushadd_gateway_mock.call_count == 0

    def test_empty_value_no_call_push_gateway(self, use_gateway_mock):
        url = "http://pushgateway.com"
        counter_name = "flow_grid_rows"
        task = _GaugeToGatewayBase(pushgateway_url=url, counter_name=counter_name)
        task.run(values=[], labels=[])
        assert use_gateway_mock.call_count == 0

    def test_call_pushgateway_one_when_no_grouping_key(self, push_mock):
        url = "http://pushgateway.com"
        counter_name = "flow_grid_rows"
        task = _GaugeToGatewayBase(
            pushgateway_url=url, counter_name=counter_name, grouping_key=[]
        )
        task.run(
            values=[1, 2, 3],
            labels=[
                {"key1": "label1_1", "key2": "label2_1"},
                {"key1": "label1_2", "key2": "label2_2"},
                {"key1": "label1_3", "key2": "label2_"},
            ],
        )
        assert push_mock.call_count == 1

    def test_call_pushgateway_one_when_grouping_key_same_values(self, push_mock):
        url = "http://pushgateway.com"
        counter_name = "flow_grid_rows"
        task = _GaugeToGatewayBase(
            pushgateway_url=url, counter_name=counter_name, grouping_key=["key1"]
        )
        task.run(
            values=[1, 2, 3],
            labels=[
                {"key1": "label1_1", "key2": "label2_1"},
                {"key1": "label1_1", "key2": "label2_2"},
                {"key1": "label1_1", "key2": "label2_"},
            ],
        )
        assert push_mock.call_count == 1

    def test_call_pushgateway_twice_when_grouping_key_differents_values(
        self, push_mock
    ):
        url = "http://pushgateway.com"
        counter_name = "flow_grid_rows"
        task = _GaugeToGatewayBase(
            pushgateway_url=url, counter_name=counter_name, grouping_key=["key1"]
        )
        task.run(
            values=[1, 2, 3],
            labels=[
                {"key1": "label1_1", "key2": "label2_1"},
                {"key1": "label1_1", "key2": "label2_2"},
                {"key1": "label1_2", "key2": "label2_3"},
            ],
        )
        assert push_mock.call_count == 2


class TestPushGaugeToGateway:
    def test_push_to_gateway(self, use_gateway_mock):
        url = "http://my-pushgateway.com"
        counter_name = "flow_grid_rows"
        job_name = "table_check"
        task = PushGaugeToGateway(
            pushgateway_url=url, counter_name=counter_name, job_name=job_name
        )
        task.run(values=[1], labels=[{"collection": "table1"}])
        assert use_gateway_mock.call_count == 1
        assert use_gateway_mock.call_args.args[0] == "PUT"


class TestPushAddGaugeToGateway:
    def test_pushadd_to_gateway(self, use_gateway_mock):
        url = "http://my-pushgateway.com"
        counter_name = "flow_grid_rows"
        job_name = "table_check"
        task = PushAddGaugeToGateway(
            pushgateway_url=url,
            counter_name=counter_name,
            job_name=job_name,
        )
        task.run(values=[1], labels=[{"collection": "table1"}])
        assert use_gateway_mock.call_count == 1
        assert use_gateway_mock.call_args.args[0] == "POST"
