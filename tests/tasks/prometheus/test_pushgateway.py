from unittest.mock import MagicMock
import prometheus_client
import prometheus_client.exposition
import pytest
from prefect.tasks.prometheus import PushGaugeToGateway, PushMode


@pytest.fixture
def use_gateway_mock(monkeypatch):
    pushaddgateway = MagicMock()
    monkeypatch.setattr(
        prometheus_client.exposition,
        "_use_gateway",
        pushaddgateway,
    )
    return pushaddgateway


class TestPushGauge:
    def test_can_instanciate_PushGaugeToGateway(self):
        task = PushGaugeToGateway()
        assert task is not None

    def test_can_initialize_pushgateway_url(self):
        url = "http://pushgateway.com"
        task = PushGaugeToGateway(pushgateway_url=url)
        assert task.pushgateway_url == url

    def test_can_initialize_counter_name(self):
        counter_name = "requests-per-second"
        task = PushGaugeToGateway(counter_name=counter_name)
        assert task.counter_name == counter_name

    def test_can_initialize_counter_description(self):
        counter_description = "Number of request per second"
        task = PushGaugeToGateway(counter_description=counter_description)
        assert task.counter_description == counter_description

    def test_can_initialize_job_name(self):
        job_name = "my-job"
        task = PushGaugeToGateway(job_name=job_name)
        assert task.job_name == job_name

    def test_can_initialize_with_kwarg(self):
        task = PushGaugeToGateway(name="My push gateway")
        assert task.name == "My push gateway"

    def test_raise_exception_when_url_missing(self):
        task = PushGaugeToGateway(name="My push gateway")
        with pytest.raises(ValueError) as ex:
            task.run()
            assert "pushgateway_url" in str(ex.value)

    def test_raise_exception_when_conter_name_missing(self):
        url = "http://pushgateway.com"
        task = PushGaugeToGateway(pushgateway_url=url)
        with pytest.raises(ValueError) as ex:
            task.run()
            assert "counter_name" in str(ex.value)

    def test_raise_exception_when_len_value_diff_label(self):
        url = "http://pushgateway.com"
        counter_name = "flow_grid_rows"
        task = PushGaugeToGateway(pushgateway_url=url, counter_name=counter_name)
        with pytest.raises(ValueError) as ex:
            task.run(values=[1], labels=[])
            assert "Values and labels" in str(ex.value)

    def test_empty_value_no_call_push_gateway(
        self, push_gateway_mock, pushadd_gateway_mock
    ):
        url = "http://pushgateway.com"
        counter_name = "flow_grid_rows"
        task = PushGaugeToGateway(pushgateway_url=url, counter_name=counter_name)
        task.run(values=[], labels=[])
        assert push_gateway_mock.call_count == 0
        assert pushadd_gateway_mock.call_count == 0

    def test_empty_value_no_call_push_gateway(self, use_gateway_mock):
        url = "http://pushgateway.com"
        counter_name = "flow_grid_rows"
        task = PushGaugeToGateway(pushgateway_url=url, counter_name=counter_name)
        task.run(values=[], labels=[])
        assert use_gateway_mock.call_count == 0

    def test_push_to_gateway(self, use_gateway_mock):
        url = "http://my-pushgateway.com"
        counter_name = "flow_grid_rows"
        job_name = "table_check"
        task = PushGaugeToGateway(
            pushgateway_url=url, counter_name=counter_name, job_name=job_name
        )
        task.run(values=[1], labels=[{"collection": "table1"}], action=PushMode.Push)
        assert use_gateway_mock.call_count == 1
        assert use_gateway_mock.call_args.args[0] == "PUT"

    def test_pushadd_to_gateway(self, use_gateway_mock):
        url = "http://my-pushgateway.com"
        counter_name = "flow_grid_rows"
        job_name = "table_check"
        task = PushGaugeToGateway(
            pushgateway_url=url,
            counter_name=counter_name,
            job_name=job_name,
        )
        task.run(values=[1], labels=[{"collection": "table1"}], action=PushMode.PushAdd)
        assert use_gateway_mock.call_count == 1
        assert use_gateway_mock.call_args.args[0] == "POST"
