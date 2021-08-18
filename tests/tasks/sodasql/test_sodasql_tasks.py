from unittest.mock import MagicMock

import pytest

from prefect.tasks.sodasql import SodaSQLScan


class TestSodaSQLScan:
    def test_construction_provide_scan_and_warehouse(self):
        expected_scan_def = "/foo/scan.yml"
        expected_warehouse_def = "/foo/warehouse.yml"
        soda_sql_scan_task = SodaSQLScan(
            scan_def="/foo/scan.yml", warehouse_def="/foo/warehouse.yml"
        )
        assert soda_sql_scan_task.scan_def == expected_scan_def
        assert soda_sql_scan_task.warehouse_def == expected_warehouse_def

    def test_construction_no_scan_and_warehouse(self):
        soda_sql_scan_task = SodaSQLScan()
        assert soda_sql_scan_task.scan_def is None
        assert soda_sql_scan_task.warehouse_def is None

    def test_run_no_scan_and_warehouse(self):
        soda_sql_scan_task = SodaSQLScan()
        with pytest.raises(ValueError):
            soda_sql_scan_task.run()

    def test_run_non_existing_scan_file_and_non_existing_warehouse_file(
        self, monkeypatch
    ):
        non_existing_scan_file = "/foo/scan.yml"
        non_existing_warehouse_file = "/foo/warehouse.yml"
        sb_mock = MagicMock()
        sb_mock.side_effect = AttributeError
        monkeypatch.setattr("prefect.tasks.sodasql.sodasql_tasks.ScanBuilder", sb_mock)
        soda_sql_scan_task = SodaSQLScan(
            scan_def=non_existing_scan_file, warehouse_def=non_existing_warehouse_file
        )
        with pytest.raises(AttributeError):
            soda_sql_scan_task.run()

    def test_run_invalid_scan_dict_and_invalid_warehouse_dict(self, monkeypatch):
        invalid_scan_dict = {"foo": "test"}
        invalid_warehouse_dict = {"foo": "test"}
        sb_mock = MagicMock()
        sb_mock.side_effect = AssertionError
        monkeypatch.setattr("prefect.tasks.sodasql.sodasql_tasks.ScanBuilder", sb_mock)
        soda_sql_scan_task = SodaSQLScan(
            scan_def=invalid_scan_dict, warehouse_def=invalid_warehouse_dict
        )
        with pytest.raises(AssertionError):
            soda_sql_scan_task.run()
