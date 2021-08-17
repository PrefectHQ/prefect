def exceptions_equal(a, b):
    if a == b:
        return True
    return type(a) == type(b) and getattr(a, "args", None) == getattr(b, "args", None)
