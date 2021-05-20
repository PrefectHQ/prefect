import pytest

from prefect import Flow, Task, task
from prefect.utilities import edges, tasks

ALL_ANNOTATIONS = [edges.unmapped, edges.mapped, edges.flatten]


class TestEdgeAnnotations:
    def test_unmapped(self):
        ea = edges.unmapped(Task())
        assert ea.annotations == {"mapped": False}

    def test_mapped(self):
        ea = edges.mapped(Task())
        assert ea.annotations == {"mapped": True}

    def test_flat(self):
        ea = edges.flatten(Task())
        assert ea.annotations == {"flattened": True}

    def test_multiple_annotations(self):
        ea = edges.mapped(edges.flatten(edges.unmapped(edges.mapped(Task()))))
        assert ea.annotations == {"flattened": True, "mapped": True}

    @pytest.mark.parametrize("edge_annotation", ALL_ANNOTATIONS)
    def test_as_task_unpacks_unmapped_objects(self, edge_annotation):
        t1 = Task()
        annotated = edge_annotation(t1)
        assert tasks.as_task(annotated) is t1
        assert tasks.as_task(annotated).auto_generated is False


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

    def test_flat_applied(self):
        with Flow("test") as flow:
            z = add.map(x=edges.flatten([[1], [2, 3]]), y=edges.unmapped(100))

        state = flow.run()
        assert state.result[z].result == [101, 102, 103]

    def test_flat_applied_to_unnested_list(self):
        with Flow("test") as flow:
            z = add.map(x=edges.flatten([1, 2, 3]), y=edges.unmapped(100))

        state = flow.run()
        assert state.result[z].result == [101, 102, 103]

    def test_flat_applied_to_constant(self):
        with Flow("test") as flow:
            z = add.map(x=[1, 2, 3], y=edges.unmapped(edges.flatten(100)))

        state = flow.run()
        assert state.result[z].result == [101, 102, 103]

    def test_multiple_annotations_applied(self):
        with Flow("test") as flow:
            z = add(x=edges.mapped(edges.flatten([[1], [2, 3]])), y=edges.unmapped(100))

        state = flow.run()
        assert state.result[z].result == [101, 102, 103]
