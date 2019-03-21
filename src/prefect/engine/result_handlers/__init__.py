"""
Result handler is simply a specific implementation of a `read` / `write` interface for handling data.
The only requirement for a Result handler implementation is that the `write` method returns a JSON-compatible object.
"""

from prefect.engine.result_handlers.result_handler import ResultHandler
from prefect.engine.result_handlers.json_result_handler import JSONResultHandler
from prefect.engine.result_handlers.local_result_handler import LocalResultHandler

try:
    from prefect.engine.result_handlers.gcs_result_handler import GCSResultHandler
except ImportError:
    pass
