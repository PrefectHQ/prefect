import abc
from prometheus_client import (
    CollectorRegistry,
    Gauge,
    pushadd_to_gateway,
    push_to_gateway,
)
from typing import Dict, List, Optional
from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class _GaugeToGatewayBase(Task):
    @abc.abstractmethod
    def _push(self, **push_args):
        pass

    def __init__(
        self,
        pushgateway_url: str = None,
        counter_name: str = None,
        counter_description: str = None,
        grouping_key: List[str] = None,
        job_name: str = None,
        **kwargs,
    ):
        self.pushgateway_url = pushgateway_url
        self.counter_name = counter_name
        self.counter_description = counter_description
        self.job_name = job_name
        self.grouping_key = grouping_key
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "pushgateway_url",
        "counter_name",
        "counter_description",
        "job_name",
        "grouping_key",
    )
    def run(
        self,
        values: List[float],
        labels: List[Dict[str, str]],
        pushgateway_url: str = None,
        counter_name: str = None,
        counter_description: str = None,
        grouping_key: Optional[List[str]] = None,
        job_name: str = None,
    ) -> None:
        """
        Push a Gauge to prometheus [PushGateway](ttps://prometheus.io/docs/practices/pushing/).
        This will unpack the values and labels to create all the a collector that will be pushed
        to pushgateway.

        Args:
            - values (List[float]): List of the values to push
            - labels (List[Dict[str, str]]): List of the labels to push attached to the values
            - pushgateway_url (str, optional): Url of the prometheus pushgateway instance
            - counter_name (str, optional): Name of the counter
            - counter_description (str, optional): description of the counter
            - grouping_key (str, optional): List of the key used to calculate the grouping key
            - job_name (str, optional): Name of the job

        Returns:
            - None

        Raises:
            - ValueError: if pushgateway_url or counter_name are empty and values and labels list
                    doesn't have the same length
        """
        if not pushgateway_url:
            raise ValueError("You need to provide the pushgateway_url parameter.")

        if not counter_name:
            raise ValueError("You need to provide the counter_name parameter.")

        if not counter_description:
            counter_description = counter_name

        if len(values) != len(labels):
            raise ValueError(
                f"Values and labels need to have the same lenght. Values lenght is {len(values)}, "
                f"labels lenght is {len(labels)}."
            )

        if len(values) == 0 or len(labels) == 0:
            return

        grouping_key_values = (
            {key: labels[0][key] for key in grouping_key} if grouping_key else {}
        )

        registry = CollectorRegistry()
        g = Gauge(
            counter_name,
            counter_description,
            labelnames=labels[0].keys(),
            registry=registry,
        )

        for k, v in zip(labels, values):
            g.labels(**k).set(v)

        self._push(
            gateway=pushgateway_url,
            job=job_name,
            grouping_key=grouping_key_values,
            registry=registry,
        )


class PushGaugeToGateway(_GaugeToGatewayBase):
    """
    Task that allow you to push a Gauge to prometheus [PushGateway]
    (https://prometheus.io/docs/practices/pushing/).This method is using the
    [prometheus_client](https://github.com/prometheus/client_python#exporting-to-a-pushgateway).

    This is a push mode task that it will remove all previous items that match the grouping key.

    Some of the main usage of that task is to allow to push inside of your workflow to prometheus like
    number of rows, quality of the values or anything you want to monitor.

    Args:
        - pushgateway_url (str, optional): Url of the prometheus pushgateway instance
        - counter_name (str, optional): Name of the counter
        - counter_description (str, optional): description of the counter
        - grouping_key (str, optional): List of the key used to calculate the grouping key
        - job_name (str, optional): Name of the job
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor

    """

    def __init__(
        self,
        pushgateway_url: str = None,
        counter_name: str = None,
        counter_description: str = None,
        grouping_key: List[str] = None,
        job_name: str = None,
        **kwargs,
    ):
        super().__init__(
            pushgateway_url=pushgateway_url,
            counter_name=counter_name,
            counter_description=counter_description,
            job_name=job_name,
            grouping_key=grouping_key,
            **kwargs,
        )

    def _push(self, **push_args):
        push_to_gateway(**push_args)


class PushAddGaugeToGateway(_GaugeToGatewayBase):
    """
    Task that allow you to push add a Gauge to prometheus [PushGateway]
    (https://prometheus.io/docs/practices/pushing/). This method is using the
    [prometheus_client](https://github.com/prometheus/client_python#exporting-to-a-pushgateway).

    This is a push add mode task that will add value into the same grouping key.

    Some of the main usage of that task is to allow to push inside of your workflow to prometheus like
    number of rows, quality of the values or anything you want to monitor.

    Args:
        - pushgateway_url (str, optional): Url of the prometheus pushgateway instance
        - counter_name (str, optional): Name of the counter
        - counter_description (str, optional): description of the counter
        - grouping_key (str, optional): List of the key used to calculate the grouping key
        - job_name (str, optional): Name of the job
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor

    """

    def __init__(
        self,
        pushgateway_url: str = None,
        counter_name: str = None,
        counter_description: str = None,
        grouping_key: List[str] = None,
        job_name: str = None,
        **kwargs,
    ):
        super().__init__(
            pushgateway_url=pushgateway_url,
            counter_name=counter_name,
            counter_description=counter_description,
            job_name=job_name,
            grouping_key=grouping_key,
            **kwargs,
        )

    def _push(self, **push_args):
        pushadd_to_gateway(**push_args)


# class PushAddGaugeToGateway(_GaugeToGatewayBase):
#     def _push(self, **push_args):
#         pushadd_to_gateway(**push_args)
