import importlib
import sys

import prometheus_client
import pytest
from prometheus_client import CollectorRegistry


@pytest.mark.benchmark(group="imports")
def bench_import_prefect(benchmark):
    def import_prefect():
        # To get an accurate result, we want to import the module from scratch each time
        # Remove the module from sys.modules if it's there
        prefect_modules = [key for key in sys.modules if key.startswith("prefect")]
        for module in prefect_modules:
            del sys.modules[module]

        # Clear importlib cache
        importlib.invalidate_caches()

        # reset the prometheus registry to clear any previously measured metrics
        prometheus_client.REGISTRY = CollectorRegistry(auto_describe=True)

        import prefect  # noqa

    benchmark(import_prefect)


@pytest.mark.timeout(180)
@pytest.mark.benchmark(group="imports")
def bench_import_prefect_flow(benchmark):
    def import_prefect_flow():
        # To get an accurate result, we want to import the module from scratch each time
        # Remove the module from sys.modules if it's there
        prefect_modules = [key for key in sys.modules if key.startswith("prefect")]
        for module in prefect_modules:
            del sys.modules[module]

        # Clear importlib cache
        importlib.invalidate_caches()

        # reset the prometheus registry to clear any previously measured metrics
        prometheus_client.REGISTRY = CollectorRegistry(auto_describe=True)

        from prefect import flow  # noqa

    benchmark(import_prefect_flow)
