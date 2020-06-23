import pytest

from prefect import Flow, Task, task
from prefect.utilities import edges, tasks

ALL_ANNOTATIONS = {edges.unmapped, edges.mapped, edges.flat}


class TestEdgeAnnotations:
    def test_unmapped():
        ea = edges.unmapped(Task())
        assert ea.annotations == {"mapped": False}

    def test_mapped():
        ea = edges.mapped(Task())
        assert ea.annotations == {"mapped": True}

    def test_flat():
        ea = edges.flat(Task())
        assert ea.annotations == {"flat": True}

    def test_multiple_annotations():
        ea = edges.mapped(edges.flat(edges.unmapped(edges.mapped(Task()))))
        assert ea.annotations == {"flat": True, "mapped": True}

    @pytest.mark.parametrize("edge_annotation", ALL_ANNOTATIONS)
    def test_as_task_unpacks_unmapped_objects(edge_annotation):
        t1 = Task()
        annotated = edge_annotation(t1)
        assert tasks.as_task(annotated) is t1
        assert tasks.as_task(annotated).auto_generated is False

    @pytest.mark.parametrize("edge_annotation", ALL_ANNOTATIONS)
    def test_unmapped_converts_its_argument_to_task(edge_annotation):
        annotated = edge_annotation(5)
        assert isinstance(annotated.task, Task)


@task
def add(x, y):
    return x + y


class TestFlow:
    def test_unmapped_applied(self):

        with Flow("test") as flow:
            z = add.map(x=[1, 2, 3], y=edges.unmapped(100))

        state = flow.run()
        assert state.result[z].result == [101, 102, 103]

    def test_mapped_applied(self):
        with Flow("test") as flow:
            z = add(x=edges.mapped([1, 2, 3]), y=100)

        state = flow.run()
        assert state.result[z].result == [101, 102, 103]
