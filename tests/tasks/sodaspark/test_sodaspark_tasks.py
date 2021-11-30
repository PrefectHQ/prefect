from unittest.mock import MagicMock


import pytest
from pyspark.sql import SparkSession

from prefect.tasks.sodaspark import SodaSparkScan


class TestSodaSparkScan:
    def test_construction_provide_scan_and_df(self):
        expected_scan_def = "/foo/bar.yaml"
        expected_df = SparkSession.builder.getOrCreate().createDataFrame(
            [{"id": 123, "value": "foo"}, {"id": 456, "value": "bar"}]
        )
        soda_spark_scan_task = SodaSparkScan(scan_def=expected_scan_def, df=expected_df)

        assert soda_spark_scan_task.scan_def == expected_scan_def
        assert soda_spark_scan_task.df == expected_df

    def test_construction_no_scan_and_df(self):
        soda_spark_scan_task = SodaSparkScan()

        assert soda_spark_scan_task.scan_def is None
        assert soda_spark_scan_task.df is None

    # @pytest.mark.skip(reason="Requires PySpark and Java to be installed")
    def test_run_no_scan(self):
        df = SparkSession.builder.getOrCreate().createDataFrame(
            [{"id": 123, "value": "foo"}, {"id": 456, "value": "bar"}]
        )
        soda_spark_scan_task = SodaSparkScan(df=df)

        with pytest.raises(ValueError) as exc:
            soda_spark_scan_task.run()
        assert "scan_def cannot be None" in str(exc)

    def test_run_no_df(self):
        soda_spark_scan_task = SodaSparkScan(scan_def="/foo/bar.yaml")
        with pytest.raises(ValueError) as exc:
            soda_spark_scan_task.run()
        assert "df cannot be None" in str(exc)

    # @pytest.mark.skip(reason="Requires PySpark and Java to be installed")
    def test_run_invalid_scan(self, monkeypatch):
        scan_def = "invalid scan definition"
        df = SparkSession.builder.getOrCreate().createDataFrame(
            [{"id": 123, "value": "foo"}, {"id": 456, "value": "bar"}]
        )
        soda_spark_scan_task = SodaSparkScan(scan_def=scan_def, df=df)
        with pytest.raises(AttributeError):
            soda_spark_scan_task.run()

    def test_run_invalid_df(self, monkeypatch):
        scan_def = """
        table_name: demodata
        metrics:
        - row_count
        - max
        - min_length
        tests:
        - row_count > 0
        """
        df = "not a valid df"
        soda_spark_scan_task = SodaSparkScan(scan_def=scan_def, df=df)
        with pytest.raises(AttributeError):
            soda_spark_scan_task.run()

    # @pytest.mark.skip(reason="Requires PySpark and Java to be installed")
    def test_run_valid_scan_and_df_with_measurements(self):
        scan_def = """
        table_name: demodata
        metrics:
        - row_count
        - max
        - min_length
        tests:
        - row_count > 0
        """
        df = SparkSession.builder.getOrCreate().createDataFrame(
            [{"id": 123, "value": "foo"}, {"id": 456, "value": "bar"}]
        )
        soda_spark_scan_task = SodaSparkScan(scan_def=scan_def, df=df)
        res = soda_spark_scan_task.run()

        assert hasattr(res, "measurements")

    # @pytest.mark.skip(reason="Requires PySpark and Java to be installed")
    def test_run_valid_scan_and_df_with_errors(self):
        scan_def = """
        table_name: demodata
        metrics:
        - row_count
        - max
        - min_length
        tests:
        - row_count == 0
        """
        df = SparkSession.builder.getOrCreate().createDataFrame(
            [{"id": 123, "value": "foo"}, {"id": 456, "value": "bar"}]
        )
        soda_spark_scan_task = SodaSparkScan(scan_def=scan_def, df=df)
        res = soda_spark_scan_task.run()

        assert hasattr(res, "errors")
