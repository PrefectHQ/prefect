import pytest

pytest.importorskip("boto3")
pytest.importorskip("botocore")
pytest.importorskip("dask_cloudprovider")
pytest.importorskip("dask_kubernetes")
pytest.importorskip("kubernetes")
pytest.importorskip("yaml")
