import peewee
import pytest
import sqlalchemy as sa
from prefect.models import (
    Namespace,
    FlowModel,
    TaskModel,
    FlowRunModel,
    TaskRunModel,
    TaskResultModel,)
import pytest
import prefect
import prefect.models as models
from prefect.utilities import (database as db, state)
import sqlalchemy as sa
import transitions


class SimpleState(state.State):
    STATE1 = _default_state = '1'
    STATE2 = '2'
    STATE3 = '3'
    _all_states = [STATE1, STATE2, STATE3]
    _transitions = [
        state.Transition(trigger='to_1', source=[STATE2], dest=STATE1),
        state.Transition(trigger='to_2', source=[STATE1], dest=STATE2),
        state.Transition(trigger='to_3', source=[STATE1, STATE2], dest=STATE3),
    ]


class StateModel(models.Base):
    __tablename__ = 'test_state_model'
    state = sa.Column(
        models.StateType(state_class=SimpleState),
        default=SimpleState._default_state)


class SimpleModel(models.Base):
    __tablename__ = 'test_methods_model'
    a = sa.Column(sa.Integer)
    b = sa.Column(sa.String)


class EncryptionModel(models.Base):
    __tablename__ = 'test_encryption_model'
    str1 = sa.Column(
        models.EncryptedStringType(encryption_key='abc'), nullable=True)
    str2 = sa.Column(
        models.EncryptedStringType(encryption_key='abc'), nullable=True)
    szd1 = sa.Column(models.SerializedType(encryption_key='abc'), nullable=True)
    szd2 = sa.Column(models.SerializedType(encryption_key='abc'), nullable=True)


@pytest.fixture(scope='module', autouse=True)
def setup():
    for model in [SimpleModel, EncryptionModel, StateModel]:
        model.__table__.create(db.engine)
    for a in range(5):
        for b in ['hi', 'bye']:
            SimpleModel.create(a=a, b=b)


class TestStateType:

    def test_state(self):
        # create with string
        s = StateModel.create(state='1')
        assert isinstance(s.state, SimpleState)

        # store string, but assign to state
        s.state = '1'
        assert isinstance(s.state, str)
        # state created on save
        s.save()
        assert isinstance(s.state, SimpleState)

        s.state = SimpleState('2')
        s.save()
        assert isinstance(s.state, SimpleState)

        # call transition methods
        assert s.state == '2'
        s.state.to_3()
        assert s.state == '3'

        # errors
        with pytest.raises(transitions.MachineError):
            assert s.state.to_1()


class TestModelMethods:

    def test_create_and_repr(self):
        m = SimpleModel.create(a=1, b='hi')
        assert repr(m) == 'SimpleModel({})'.format(m.id)

    def test_find(self):
        m = SimpleModel.find(id=3)
        assert m.id == 3
        n = SimpleModel.find(id='abc')
        assert n is None
        with pytest.raises(ValueError):
            SimpleModel.find(id='abc', error_if_missing=True)

    def test_update(self):
        m = SimpleModel.find(id=1)
        assert m.b == 'hi'
        m.update(b='hello')
        assert SimpleModel.find(id=1).b == 'hello'

    def test_delete(self):
        m = SimpleModel.find(id=4)
        m.delete()
        assert SimpleModel.find(id=4) is None

    def test_where(self):
        assert len(SimpleModel.where(SimpleModel.a == 4)) == 2
        assert len(SimpleModel.where(SimpleModel.a == 4, SimpleModel.b == 'hi')) == 1
        assert len(SimpleModel.where(a=4, b='hi')) == 1

    def test_first(self):
        assert isinstance(SimpleModel.first(a=4), SimpleModel)
        assert SimpleModel.first(a=4, order_by=SimpleModel.b).b == 'bye'

    def test_get_or_build(self):
        count = SimpleModel.count(a=4, b='hi')
        assert count == 1
        # matches multiple
        with pytest.raises(ValueError):
            SimpleModel.get_or_build(a=4)

        m = SimpleModel.get_or_build(a=4, b='hi')
        assert m.a == 4 and m.b == 'hi'
        # no new models were added
        assert SimpleModel.count(a=4, b='hi') == count

        # build a new model but don't add it to the database
        m = SimpleModel.get_or_build(a=20, b='hello')
        assert m.id is None
        assert m.b == 'hello'
        assert SimpleModel.count(a=4, b='hi') == count

    def test_get_or_create(self):
        count = SimpleModel.count(a=4, b='hi')
        assert count == 1
        # matches multiple
        with pytest.raises(ValueError):
            SimpleModel.get_or_create(a=4)

        m = SimpleModel.get_or_create(a=4, b='hi')
        assert m.a == 4 and m.b == 'hi'
        # no new models were added
        assert SimpleModel.count(a=4, b='hi') == count

        m = SimpleModel.get_or_create(a=20, b='hello')
        assert m == SimpleModel.find(m.id)

    def test_encryption_and_serialization(self):
        f = prefect.Flow(name='test')

        # test that strings, bytes, and objects can be stored
        t = EncryptionModel.create(str1='hi', str2='hi', szd1=f, szd2=f)

        # show that values were all encrypted
        db_values = db.engine.execute(
            sa.text(
                'select str1, str2, szd1, szd2 '
                'from test_encryption_model where id = :id'),
            id=t.id).fetchone()

        assert db_values[0] != 'hi'
        assert db_values[1] != 'hi'
        assert isinstance(db_values[2], bytes)
        assert isinstance(db_values[3], bytes)

        # encryption values should be randomized due to the random IV, even when
        # the same encryption key is used
        assert db_values[0] != db_values[1]
        assert db_values[2] != db_values[3]

        # recover object from the database
        t = EncryptionModel.find(t.id)

        # show that values were decrypted / deserialized
        assert t.str1 == t.str2 == 'hi'
        assert t.szd1 == t.szd2 == f

    def test_session_flush(self):
        """
        When a model is created, it can exist in the session and be committed
        when another method is called, like .where(). Make sure the session is
        expunged before each transaction starts.
        """
        sql = 'select count(*) from test_methods_model'
        count = db.engine.execute(sql).fetchone()[0]
        model = SimpleModel()
        assert SimpleModel.count() == count



@pytest.fixture(scope='session')
def env():
    # build namespaces
    system_namespace = Namespace.create(name='system')
    test_namespace = Namespace.create(name='test')
    namespaces = dict(system=system_namespace, test=test_namespace)

    # build Flows
    sys_flow1 = FlowModel.create(
        namespace=system_namespace, name='f1', version=1)
    sys_flow2 = FlowModel.create(
        namespace=system_namespace, name='f2', version=1, archived=True)
    flow1 = FlowModel.create(namespace=test_namespace, name='f1', version=1)
    flow2 = FlowModel.create(namespace=test_namespace, name='f2', version=1)
    flow12 = FlowModel.create(namespace=test_namespace, name='f1', version=2)
    flows = dict(sys1=sys_flow1, sys2=sys_flow2, f1=flow1, f2=flow2, f12=flow12)

    # add tasks
    for flow in flows.values():
        TaskModel.create(name='t1', flow=flow)
        TaskModel.create(name='t2', flow=flow)
        TaskModel.create(name='t3', flow=flow)

    # create FlowRuns
    params = {'a': 1, 'b': '2', 'c': [3, 4, 5], 4: 'd'}
    for flow in flows.values():
        for i in [1, 2]:
            flow_run = FlowRunModel.create(flow=flow, params=params)

            # create TaskRuns
            for t in flow.tasks:
                for run_number in [1, 2]:
                    tr = TaskRunModel.create(
                        flow_run=flow_run, task=t, run_number=run_number)
                    TaskResultModel.create(
                        task_run=tr, index='<None>', serialized=b'x')
                    TaskResultModel.create(
                        task_run=tr, index='<1>', serialized=b'y')

    yield dict(
        ns=namespaces,
        f=flows,)


def test_create_flow_new_namespace():
    """
    Creating a FlowModel should automatically create the provided Namespace,
    if it doesn't exist already.
    """
    new_namespace = Namespace(name='abc')
    flow = FlowModel(namespace=new_namespace, name='1', version=1)
    assert not Namespace.where(Namespace.name == 'abc')
    flow.save()
    assert Namespace.where(Namespace.name == 'abc')


def test_unique_constraint(env):
    """
    Test that we are prevented from recreating existing objects
    """
    with pytest.raises(sa.exc.IntegrityError):
        Namespace.create(namespace='system')

    with pytest.raises(sa.exc.IntegrityError):
        FlowModel.create(namespace=env['ns']['test'], name='f1', version=1)

    with pytest.raises(sa.exc.IntegrityError):
        TaskModel.create(name='t1', flow=env['f']['f1'])


def test_walk_relationships(env):
    """
    Walk the hierarchy of objects to confirm foreign key lookups are intact
    """
    namespace = env['ns']['test']

    # walk namespace -> flow -> tasks
    flow = namespace.flows[0]
    assert flow.name == 'f1'
    assert flow.namespace == namespace
    assert flow.tasks[0].name == 't1'

    # walk flow -> flowrun -> taskrun -> taskresult
    r = flow.flow_runs[0].task_runs[0].task_results[0]
    assert r.serialized == b'x'

    # walk taskresult -> taskrun -> flowrun -> flow -> namespace
    assert r.task_run.flow_run.flow.namespace.name == 'test'


def test_delete_children(env):
    """
    test that deleting a parent object deletes all children
    """

    # with db.transaction() as s:
    task_result_count = TaskResultModel.count()
    env['f']['f1'].flow_runs[0].task_runs[0].delete()
    assert task_result_count != TaskResultModel.count()

    flow_count = FlowModel.count()
    task_count = TaskModel.count()
    flow_run_count = FlowRunModel.count()
    task_run_count = TaskRunModel.count()
    task_result_count = TaskResultModel.count()

    # delete a flow
    env['f']['f2'].delete()

    assert flow_count != FlowModel.count()
    assert task_count != TaskModel.count()
    assert flow_run_count != FlowRunModel.count()
    assert task_run_count != TaskRunModel.count()
    assert task_result_count != TaskResultModel.count()
