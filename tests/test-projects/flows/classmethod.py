from prefect import flow


class Foo:
    @classmethod
    @flow
    def bar(cls):
        return "foobar"
