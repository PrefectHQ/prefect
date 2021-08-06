import abc
from prometheus_client import (
    CollectorRegistry,
    Gauge,
    pushadd_to_gateway,
    push_to_gateway,
)
from collections import namedtuple
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
        Push a Gauge to prometheus [PushGateway](https://prometheus.io/docs/practices/pushing/).
        This will unpack the values and labels to create all the a collector that will be pushed
        to pushgateway.

        The following example is checking the data quality of a dataframe and output the metrics
        for the job to the pushgateway

        example:
        ```
        from typing import Any, Dict, List, Tuple
        import pandas as pd
        from prefect import task, Flow, Parameter
        from prefect.tasks.prometheus import PushAddGaugeToGateway


        @task
        def read_csv(path: str) -> pd.DataFrame:
            return pd.read_csv(path)


        @task
        def check_na(
            df: pd.DataFrame, dataframe_name: str
        ) -> Tuple[List[Dict[str, Any]], List[float]]:
            total_rows = df.shape[0]
            lkeys = []
            lvalues = []
            for c in df.columns:
                na_values = len(df[df[c].isna()][c])
                key = {"df": dataframe_name, "column": c}
                lkeys.append(key)
                lvalues.append(na_values / total_rows)

            return (lkeys, lvalues)


        with Flow("Check_Data") as flow:
            source_path = Parameter(name="sourcePath", required=True)
            name = Parameter(name="name", required=True)
            pushgateway_url = Parameter(
                name="pushgatewayUrl", default="http://localhost:9091"
            )
            df = read_csv(source_path)
            check_result = check_na(df, name)
            push_gateway = PushAddGaugeToGateway()
            push_gateway(
                values=check_result[1],
                labels=check_result[0],
                pushgateway_url=pushgateway_url,
                counter_name="null_values_percentage",
                grouping_key=["df"],
                job_name="check_data",
            )

        flow.run(parameters={"sourcePath": "sample_data.csv", "name": "mySample"})

        ```

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
                f"Values and labels need to have the same length. Values length is {len(values)}, "
                f"labels length is {len(labels)}."
            )

        if len(values) == 0 or len(labels) == 0:
            return

        GroupingValues = namedtuple(
            "GroupingValues", ["grouping_key", "labels_names", "labels", "values"]
        )

        groups = {}
        for l, v in zip(labels, values):

            grouping_key_values = (
                {key: l[key] for key in grouping_key} if grouping_key else {}
            )
            group_key_id = "-".join(grouping_key_values.values())
            group_values = groups.setdefault(
                group_key_id, GroupingValues(grouping_key_values, l.keys(), [], [])
            )
            group_values.labels.append(l)
            group_values.values.append(v)

        for group in groups.values():
            registry = CollectorRegistry()
            g = Gauge(
                counter_name,
                counter_description,
                labelnames=group.labels_names,
                registry=registry,
            )

            for k, v in zip(group.labels, group.values):
                g.labels(**k).set(v)

            self._push(
                gateway=pushgateway_url,
                job=job_name,
                grouping_key=group.grouping_key,
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
