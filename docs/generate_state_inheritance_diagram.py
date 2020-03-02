import graphviz
from prefect.engine.state import *


class StateDiagramGenerator:
    def __init__(self, filepath=".vuepress/public/state_inheritance_diagram"):
        self.nodes = set()
        self.graph = graphviz.Digraph(format="svg")
        self.filepath = filepath

    def create_node(self, state):
        if state not in self.nodes:
            self.graph.node(
                str(id(state)),
                state.__name__,
                color=state.color + "99",
                style="filled",
                colorscheme="svg",
            )
            self.nodes.add(state)

    def add_downstreams(self, state):
        self.create_node(state)

        for substate in state.__subclasses__():
            self.create_node(substate)
            self.graph.edge(str(id(state)), str(id(substate)))
            self.add_downstreams(substate)

    def generate(self, view=False):
        self.add_downstreams(State)
        self.graph.render(self.filepath, cleanup=True, view=view)


def generate_state_inheritance_diagram(view=False):
    StateDiagramGenerator().generate(view=view)


if __name__ == "__main__":
    generate_state_inheritance_diagram(view=True)
