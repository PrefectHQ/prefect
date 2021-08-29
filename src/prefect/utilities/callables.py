import inspect
from typing import Any, Callable, Dict, Tuple


def get_call_parameters(
    fn: Callable, call_args: Tuple[Any, ...], call_kwargs: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Bind a call to a function to get parameter/value mapping. Default values on the
    signature will be included if not overriden.

    Will throw an exception if the arguments/kwargs are not valid for the function
    """
    bound_signature = inspect.signature(fn).bind(*call_args, **call_kwargs)
    bound_signature.apply_defaults()
    # We cast from `OrderedDict` to `dict` because Dask will not convert futures in an
    # ordered dictionary to values during execution
    return dict(bound_signature.arguments)
