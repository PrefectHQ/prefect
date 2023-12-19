from pydantic import BaseModel

from prefect import flow, serve


class Foo(BaseModel):
    bar: str
    baz: int


class ParentFoo(BaseModel):
    foo: Foo


@flow
def child(foo: Foo = Foo(bar="hello", baz=42)):
    print(f"received {foo.bar} and {foo.baz}")


@flow(log_prints=True)
def parent(parent_foo: ParentFoo = ParentFoo(foo=Foo(bar="hello", baz=42))):
    print("I'm a parent")
    child(parent_foo.foo)


if __name__ == "__main__":
    serve(parent.to_deployment(__file__), webserver=True)
