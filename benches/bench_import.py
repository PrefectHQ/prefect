import importlib
import sys


def bench_import_prefect(benchmark):
    def import_prefect():
        # To get an accurate result, we want to import the module from scratch each time
        # Remove the module from sys.modules if it's there
        if "prefect" in sys.modules:
            del sys.modules["prefect"]

        # Clear importlib cache
        importlib.invalidate_caches()

        import prefect  # noqa

    benchmark(import_prefect)


def bench_import_prefect_flow(benchmark):
    def import_prefect_flow():
        # To get an accurate result, we want to import the module from scratch each time
        # Remove the module from sys.modules if it's there
        if "prefect" in sys.modules:
            del sys.modules["prefect"]

        # Clear importlib cache
        importlib.invalidate_caches()

        from prefect import flow  # noqa

    benchmark(import_prefect_flow)
