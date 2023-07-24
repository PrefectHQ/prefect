try:
    from pydantic.v1.decorator import ValidatedFunction
except ImportError:
    from pydantic.decorator import ValidatedFunction
