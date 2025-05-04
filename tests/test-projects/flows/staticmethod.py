from prefect import flow


class Foo:
    @staticmethod
    @flow
    def bar():
        return "foobar"
