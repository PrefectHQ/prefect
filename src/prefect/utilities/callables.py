import inspect
from typing import Callable, Dict, Any, Tuple, OrderedDict


def get_call_parameters(
    fn: Callable, call_args: Tuple[Any, ...], call_kwargs: Dict[str, Any]
) -> OrderedDict[str, Any]:
    """
    Bind a call to a function to get parameter/value mapping

    Will throw an exception if the arguments/kwargs are not valid for the function
    """
    bound_signature = inspect.signature(fn).bind(*call_args, **call_kwargs)
    bound_signature.apply_defaults()
    return bound_signature.arguments
