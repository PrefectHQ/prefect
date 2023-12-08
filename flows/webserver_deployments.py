from platform import python_version

try:
    import pydantic.v1 as pydantic
except ImportError:
    import pydantic


from prefect import __version__, flow, serve

# tests some of these things
# Models within Models
# container types --> List[str], List[dict[str, Any]]
# duplicated types

# maybe we feel meh about this
# dict[dict[dict...]]


class A(pydantic.BaseModel):
    x: int = 0


class B(pydantic.BaseModel):
    a: A = pydantic.Field(default_factory=A)


class C(pydantic.BaseModel):
    a: A = pydantic.Field(default_factory=A)


@flow(log_prints=True)
def my_flow(x: int, y: int = 1, z: str = "hello", a: A = A()) -> int:
    print(f"{python_version()=}", f"{pydantic.__version__=}", f"{__version__}")
    print(x, y, z, a)
    return x + y


if __name__ == "__main__":
    serve(my_flow.to_deployment(__file__), webserver=True)
