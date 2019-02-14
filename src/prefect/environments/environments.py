
class Environment:
    """"""
    def __init__(self) -> None:
        pass

    def build(self) -> "Environment":
        raise NotImplementedError()

    def execute(self) -> None:
        raise NotImplementedError()

    def run(self) -> None:
        raise NotImplementedError()

    def setup(self) -> None:
        raise NotImplementedError()