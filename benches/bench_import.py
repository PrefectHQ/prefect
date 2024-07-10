import importlib
import sys


def bench_import_prefect(benchmark):
    # To get an accurate result, we want to import the module from scratch each time
    # Remove the module from sys.modules if it's there
    if "prefect" in sys.modules:
        del sys.modules["prefect"]

    # Clear importlib cache
    importlib.invalidate_caches()

    def import_prefect():
        import prefect  # noqa

    benchmark(import_prefect)


def bench_import_prefect_flow(benchmark):
    # To get an accurate result, we want to import the module from scratch each time
    # Remove the module from sys.modules if it's there
    if "prefect" in sys.modules:
        del sys.modules["prefect"]

    # Clear importlib cache
    importlib.invalidate_caches()

    def import_prefect_flow():
        from prefect import flow  # noqa

    benchmark(import_prefect_flow)
