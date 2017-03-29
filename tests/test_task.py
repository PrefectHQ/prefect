import mongoengine
import prefect.exceptions
from prefect.flow import Flow
from prefect.task import Task, TaskResult
import pytest


def fn():
    """ a test function for tasks"""
    pass


class TestBasics:

    def test_create_task(self):
        """Test task creation"""

        # tasks require Flows
        with pytest.raises(ValueError) as e:
            t = Task(fn=fn)

        f = Flow('test_flow')
        t = Task(fn=fn, name='test', flow=f)
        assert t.flow_id == f.id

    def test_flow_context_manager(self):
        """Tests that flows can be used as context managers"""

        with Flow('test_flow') as f:
            t = Task(fn=fn, name='test')

            # nested context manager
            with Flow('test_flow_2') as f2:
                t2 = Task(fn=fn, name='test')

            # return to original context manager
            t3 = Task(fn=fn, name='test1')

            assert t.flow_id == f.id
            assert t in f.graph

            assert t2.flow_id == f2.id
            assert t2 in f2.graph
            assert t2 not in f.graph

            assert t3.flow is f
            assert t3 in f.graph

    def test_add_task_to_flow_after_flow_assigned(self):
        with Flow('test_flow') as f:
            t = Task(fn=fn, name='test')

        with pytest.raises(ValueError) as e:
            t2 = Task(fn=fn, name='test', flow=f)
        assert 'already exists in this Flow' in str(e)

        with pytest.raises(ValueError) as e:
            f2 = Flow('test_flow_2')
            f2.add_task(t)
        assert 'already in another Flow' in str(e)


class TestTaskRelationships:

    def test_task_relationships(self):
        """Test task relationships"""
        with Flow('test') as f:
            before = Task(fn=fn, name='before')
            after = Task(fn=fn, name='after')

        before.run_before(after)
        assert before in f.graph
        assert after in f.graph
        assert before in f.graph[after]

        # same test, calling `run_after`
        with Flow('test') as f:
            before = Task(fn=fn, name='before')
            before2 = Task(fn=fn, name='before_2')
            after = Task(fn=fn, name='after')

        after.run_after([before, before2])
        assert before in f.graph
        assert before2 in f.graph
        assert after in f.graph
        assert before in f.graph[after]
        assert before2 in f.graph[after]

    def test_detect_cycle(self):
        with Flow('test') as f:
            t1 = Task(fn=fn, name='t1')
            t2 = Task(fn=fn, name='t2')
            t3 = Task(fn=fn, name='t3')

        t1.run_before(t2)
        t2.run_before(t3)

        with pytest.raises(prefect.exceptions.PrefectError) as e:
            t3.run_before(t1)

    def test_shift_relationship_sugar(self):
        """Test task relationships with | and >> and << sugar"""
        with Flow('test') as f:
            before = Task(fn=fn, name='before')
            mid1 = Task(fn=fn, name='mid1')
            mid2 = Task(fn=fn, name='mid2')
            after = Task(fn=fn, name='after')

        (before
         | (mid1, mid2)
         | after)
        assert before in f.graph
        assert mid1 in f.graph
        assert mid2 in f.graph
        assert after in f.graph
        assert before in f.graph[mid1]
        assert before in f.graph[mid2]
        assert set([mid1, mid2]) == f.graph[after]

        with Flow('test') as f:
            before = Task(fn=fn, name='before')
            mid1 = Task(fn=fn, name='mid1')
            mid2 = Task(fn=fn, name='mid2')
            after = Task(fn=fn, name='after')

        before >> (mid1, mid2) >> after
        assert before in f.graph
        assert mid1 in f.graph
        assert mid2 in f.graph
        assert after in f.graph
        assert before in f.graph[mid1]
        assert before in f.graph[mid2]
        assert set([mid1, mid2]) == f.graph[after]

        # same test, calling `run_after`
        with Flow('test') as f:
            before = Task(fn=fn, name='before')
            mid1 = Task(fn=fn, name='mid1')
            mid2 = Task(fn=fn, name='mid2')
            after = Task(fn=fn, name='after')

        after << (mid1, mid2) << before
        assert before in f.graph
        assert mid1 in f.graph
        assert mid2 in f.graph
        assert after in f.graph
        assert before in f.graph[mid1]
        assert before in f.graph[mid2]
        assert set([mid1, mid2]) == f.graph[after]


class TestSerialization:

    def test_serialize(self):
        with Flow('test') as f:
            t1 = Task(fn=fn, name='t1')

        serialized = t1.serialize()
        t2 = Task.from_serialized(serialized)
        assert t1.id == t2.id

    def test_save(self):
        name = 'test-save-task'
        with Flow(name) as f:
            t1 = Task(fn=fn, name=name)
        t1.save()
        model = t1.to_model()
        c = mongoengine.connection.get_connection()
        collection = c[prefect.config.get('mongo', 'db')][
            model._collection.name]
        assert collection.find_one(t1.id)['name'] == name
        assert collection.find_one(t1.id)['flow_id'] == t1.flow.to_model()._id

        new_name = 'new name'
        t1.name = new_name
        t1.save()
        assert collection.find_one(t1.id)['name'] == new_name

    def test_from_id(self):
        with Flow('test') as f:
            t1 = Task(fn=fn, name='test')
        t1.save()
        with pytest.raises(mongoengine.DoesNotExist):
            t2 = Task.from_id(t1.id)

        f.save()
        t2 = Task.from_id(t1.id)
        assert t2.id == t1.id


class TestTaskResults:

    def test_task_results(self):
        with Flow('test') as f:
            t1 = Task(fn=fn, name='t1')
        assert isinstance(t1['a'], TaskResult)
        assert t1['a'].task is t1 and t1['a'].index == 'a'
