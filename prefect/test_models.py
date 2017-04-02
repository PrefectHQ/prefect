import peewee
import pytest
from prefect.models import (
    Namespace,
    FlowModel,
    TaskModel,
    FlowRunModel,
    TaskRunModel,
    TaskResultModel,)


@pytest.fixture(scope='module')
def env():
    # build namespaces
    system_namespace = Namespace.create(namespace='system')
    test_namespace = Namespace.create(namespace='test')
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
        for i in range(3):
            flowrun = FlowRunModel.create(flow=flow, params=params)

            # create TaskRuns
            for t in flow.tasks:
                for run_number in range(1, 3):
                    tr = TaskRunModel.create(
                        flowrun=flowrun, task=t, run_number=run_number)
                    TaskResultModel.create(
                        taskrun=tr, index='<None>', serialized=b'x')
                    TaskResultModel.create(
                        taskrun=tr, index='<1>', serialized=b'y')

    yield dict(
        ns=namespaces,
        f=flows,
    )


def test_unique_constraint(env):
    """
    Test that we are prevented from recreating existing objects
    """
    with pytest.raises(peewee.IntegrityError):
        Namespace.create(namespace='system')

    with pytest.raises(peewee.IntegrityError):
        FlowModel.create(namespace=env['ns']['test'], name='f1', version=1)

    with pytest.raises(peewee.IntegrityError):
        TaskModel.create(name='t1', flow=env['f']['f1'])


def test_relationships(env):
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
    r = flow.flow_runs[0].task_runs[0].results[0]
    assert r.serialized == b'x'

    # walk taskresult -> taskrun -> flowrun -> flow -> namespace
    assert r.taskrun.flowrun.flow.namespace.namespace == 'test'
