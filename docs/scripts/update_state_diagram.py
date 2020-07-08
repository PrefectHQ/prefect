"""
Updates `.vuepress/public/state_inheritance_diagram.svg` after a state hierarchy change.
"""
import os
import graphviz

from prefect.engine.state import State


graph = graphviz.Digraph(format="svg")
state_nodes = set()


def create_node(state):
    if state not in state_nodes:
        graph.node(
            str(id(state)),
            state.__name__,
            color=state.color + "99",
            style="filled",
            colorscheme="svg",
        )
        state_nodes.add(state)


def add_downstreams(state):
    create_node(state)
    for substate in state.__subclasses__():
        create_node(substate)
        graph.edge(str(id(state)), str(id(substate)))
        add_downstreams(substate)


# populate graph
add_downstreams(State)

scripts_dir = os.path.abspath(os.path.dirname(__file__))
filename = os.path.join(
    scripts_dir, "..", ".vuepress", "public", "state_inheritance_diagram.svg"
)
data = graph.pipe(format="svg")
with open(filename, "wb") as fil:
    fil.write(data)
