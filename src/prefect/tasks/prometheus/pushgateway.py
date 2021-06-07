from enum import Enum
from prometheus_client import (
    CollectorRegistry,
    Gauge,
    pushadd_to_gateway,
    push_to_gateway,
)
from typing import Dict, List, Optional
from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class PushMode(Enum):
    Push = 1
    PushAdd = 2


class PushGaugeToGateway(Task):
    """
    Task that allow you to push a Gauge to prometheus [PushGateway]
    (ttps://prometheus.io/docs/practices/pushing/).

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
        values: List[float] = [],
        labels: List[Dict[str, str]] = [],
        action: PushMode = PushMode.Push,
        pushgateway_url: str = None,
        counter_name: str = None,
        counter_description: str = None,
        grouping_key: Optional[List[str]] = None,
        job_name: str = None,
    ) -> None:
        """
        Task that allow you to push a Gauge to prometheus [PushGateway]
        (ttps://prometheus.io/docs/practices/pushing/).

        Args:
            - values (List[float]): List of the values to push
            - labels (List[Dict[str, str]]): List of the labels to push attached to the values
            - action (PushMode): Mode used to send to pushgateway. push or pushadd. Please check
                        pushgateway [python doc]
                        (https://github.com/prometheus/client_python#exporting-to-a-pushgateways)
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
                f"Values and labels need to have the same lenght. nb Values {len(values)}, "
                f"nb labels {len(labels)}, "
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

        if action == PushMode.Push:
            push_to_gateway(
                pushgateway_url,
                job=job_name,
                grouping_key=grouping_key_values,
                registry=registry,
            )
        else:
            pushadd_to_gateway(
                pushgateway_url,
                job=job_name,
                grouping_key=grouping_key_values,
                registry=registry,
            )
