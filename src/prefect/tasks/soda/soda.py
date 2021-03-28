from sodasql.scan.scan_builder import ScanBuilder

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs

from typing import Dict, Union


class SodaSQLScan(Task):
    """
    SodaSQLScan
    """

    def __init__(
        self,
        scan_def: Union[Dict, str] = None,
        warehouse_def: Union[Dict, str] = None,
        **kwargs
    ):
        """

        Args:
            scan_def:
            warehouse_def:
            **kwargs:
        """

        self.scan_def = scan_def
        self.warehouse_def = warehouse_def
        super().__init__(**kwargs)

    @classmethod
    def _get_scan_builder(
        cls, scan_def: Union[Dict, str], warehouse_def: Union[Dict, str]
    ) -> ScanBuilder:
        """"""
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
    def run(self, scan_def: Union[Dict, str], warehouse_def: Union[Dict, str]):
        """

        Args:
            scan_def:
            warehouse_def:

        Returns:

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
