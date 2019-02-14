import prefect
from prefect.environments import Environment

class LocalOnKubernetes(Environment):
    """"""
    def __init__(self) -> None:
        pass

    def build(self, flow: "prefect.Flow") -> "Environment":
        pass

    def execute(self) -> None:
        pass

    def run(self) -> None:
        pass

    def setup(self) -> None:
        pass