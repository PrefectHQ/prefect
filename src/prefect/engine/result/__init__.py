"""
The Result classes in this `prefect.engine.result` package are results used internally by the Prefect pipeline to track and store results without persistence.

If you are looking for the API docs for the result subclasses you can use to enable task return value checkpointing or to store task data, see the API docs for the [Result Subclasses in `prefect.engine.results`](results.html).
"""
import prefect
from prefect.engine.result.base import (
    Result,
    ResultInterface,
    NoResult,
    NoResultType,
    SafeResult,
)
