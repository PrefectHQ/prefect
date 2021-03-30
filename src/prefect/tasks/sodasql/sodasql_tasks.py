from sodasql.scan.scan_builder import ScanBuilder

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs

from typing import Dict, Union


class SodaSQLScan(Task):
    """
    Task for running a SodaSQL scan given a scan definition and a warehouse definition.

    Args:
        - scan_def (dict, str, optional): scan definition.
            Can be either a path a SodaSQL Scan YAML file or a dictionary.
            For more information regarding SodaSQL Scan YAML files
            refer to https://docs.soda.io/soda-sql/documentation/scan.html
        - warehouse_def (dict, str, optional): warehouse definition.
            Can be either a path to a SodaSQL Warehouse YAML file or a dictionary.
            For more information regarding SodaSQL Warehouse YAML files
            refer to https://docs.soda.io/soda-sql/documentation/warehouse.html
    """

    def __init__(
        self,
        scan_def: Union[Dict, str] = None,
        warehouse_def: Union[Dict, str] = None,
        **kwargs
    ):
        self.scan_def = scan_def
        self.warehouse_def = warehouse_def
        super().__init__(**kwargs)

    @classmethod
    def _get_scan_builder(
        cls, scan_def: Union[Dict, str], warehouse_def: Union[Dict, str]
    ) -> ScanBuilder:
        """
        Convenience method to build a SodaSQL ScanBuilder object

        Args:
            - scan_def (dict, str, optional): scan definition.
                Can be either a path a SodaSQL Scan YAML file or a dictionary.
                For more information regarding SodaSQL Scan YAML files
                refer to https://docs.soda.io/soda-sql/documentation/scan.html
            - warehouse_def (dict, str, optional): warehouse definition.
                Can be either a path to a SodaSQL Warehouse YAML file or a dictionary.
                For more information regarding SodaSQL Warehouse YAML files
                refer to https://docs.soda.io/soda-sql/documentation/warehouse.html

        Returns:
            - a SodaSQL ScanBuilder object
        """
        scan_builder = ScanBuilder()

        if isinstance(scan_def, str):
            scan_builder.scan_yml_file = scan_def
        elif isinstance(scan_def, dict):
            scan_builder.scan_yml_dict = scan_def

        if isinstance(warehouse_def, str):
            scan_builder.warehouse_yml_file = warehouse_def
        elif isinstance(warehouse_def, dict):
            scan_builder.warehouse_yml_dict = warehouse_def

        return scan_builder

    @defaults_from_attrs("scan_def", "warehouse_def")
    def run(
        self, scan_def: Union[Dict, str] = None, warehouse_def: Union[Dict, str] = None
    ):
        """
        Task run method. Execute a Scan against a Scan definition using a Warehouse definition.

        Args:
            - scan_def (dict, str, optional): scan definition.
                Can be either a path a SodaSQL Scan YAML file or a dictionary.
                For more information regarding SodaSQL Scan YAML files
                refer to https://docs.soda.io/soda-sql/documentation/scan.html
            - warehouse_def (dict, str, optional): warehouse definition.
                Can be either a path to a SodaSQL Warehouse YAML file or a dictionary.
                For more information regarding SodaSQL Warehouse YAML files
                refer to https://docs.soda.io/soda-sql/documentation/warehouse.html

        Returns:
            - A SodaSQL ScanResult object that contains all details regarding the execution
                of the scan (i.e: computed metrics, tests, errors, failures)

        Raises:
            - ValueError: if either scan_def or warehouse_def are None

        """
        if scan_def is None:
            raise ValueError(
                "Scan definition cannot be None. \
                Please provide either a path to a scan definition \
                file or a scan definition dictionary"
            )
        if warehouse_def is None:
            raise ValueError(
                "Warehouse definition cannot be None. \
                Please provide either a path to a warehouse definition \
                file or a warehouse definition dictionary"
            )
        scan_builder = self._get_scan_builder(
            scan_def=scan_def, warehouse_def=warehouse_def
        )
        scan = scan_builder.build()
        result = scan.execute()
        return result
