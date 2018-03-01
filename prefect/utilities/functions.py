import inspect


def get_var_kw_arg(fn):
    """
    Returns the name of the function argument that accepts variable
    keyword arguments (if any)
    """
    return inspect.getfullargspec(fn).varkw


def get_var_pos_arg(fn):
    """
    Returns the name of the function argument that accepts variable
    positional arguments (if any)
    """
    return inspect.getfullargspec(fn).varargs


def get_first_arg(fn):
    """
    Returns the name of the first argument of the function. If the function is
    an unbound method, this will return the argument corresponding to "self"; if
    it is a bound method, this will be the first positional argument.
    """
    sentinel = object()
    args = inspect.signature(fn).bind_partial(sentinel).arguments
    return next((k for k, a in args.items() if a is sentinel), None)
