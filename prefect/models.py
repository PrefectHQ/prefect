import datetime
import inspect
import itertools
from mongoengine import Document, EmbeddedDocument, queryset_manager
from mongoengine.fields import (
    BooleanField,
    DateTimeField,
    DictField,
    EmbeddedDocumentField,
    IntField,
    ListField,
    MapField,
    ReferenceField,
    StringField,)
import prefect
from prefect.state import State
from prefect.utilities.schedules import Schedule
from prefect.utilities.serialize import Serialized

class FlowModel(Document):
    _id = StringField(primary_key=True)
    namespace = StringField(
        default=prefect.config.get('flows', 'default_namespace'))
    name = StringField(required=True, unique_with='namespace')
    version = StringField(default='1')
    schedule = EmbeddedDocumentField(Schedule)
    params = ListField(StringField, default=tuple())
    active = BooleanField(
        default=prefect.config.getboolean('flows', 'default_active'))
    serialized = EmbeddedDocumentField(Serialized)
    graph = MapField(ListField(StringField(), default=tuple()))

    meta = {'collection': 'flowModels'}

    @queryset_manager
    def get_active(doc_cls, queryset):
        return [
            prefect.flow.Flow.from_serialized(**f['serialized'])
            for f in queryset.filter(active=True)
        ]

    def recreate_full_graph(self):
        """
        The graph is stored as a dict of {task_id: [task_id, task_id...]} pairs.
        This method looks up the tasks to recreate a graph of Task objects.
        """
        return {
            prefect.task.Task.from_id(t_id):
            set([prefect.task.Task.from_id(p) for p in pt_ids])
            for t_id, pt_ids in self.graph.items()
        }


class TaskModel(Document):
    _id = StringField(primary_key=True)
    name = StringField(required=True, unique_with='flow_id')
    flow_id = StringField(required=True)
    serialized = EmbeddedDocumentField(Serialized)

    meta = {'collection': 'taskModels'}  #, 'indexes': ['flow']}


class FlowRunModel(Document):
    _id = StringField(primary_key=True)
    flow = ReferenceField(FlowModel, required=True)
    params = MapField(EmbeddedDocumentField(Serialized), default=lambda: dict())
    generated_by = ReferenceField('TaskRunModel')
    state = StringField(default=State.PENDING, choices=list(State.all_states()))
    created = DateTimeField(default=lambda: datetime.datetime.utc_now())
    started = DateTimeField()
    finished = DateTimeField()

    meta = {'collection': 'flowRuns', 'indexes': ['state', 'created']}


class TaskRunModel(EmbeddedDocument):
    _id = StringField(primary_key=True)
    task = ReferenceField(TaskModel, required=True)
    flow_run = ReferenceField(FlowRunModel)
    state = StringField(default=State.NONE)
    run_count = IntField(default=0)
    scheduled_start = DateTimeField()
    created = DateTimeField(default=lambda: datetime.datetime.utc_now())
    started = DateTimeField()
    finished = DateTimeField()

    meta = {
        'collection': 'taskRuns',
        'indexes': ['flow_run', 'state', 'scheduled_start']
    }

    @classmethod
    def from_task_and_flowrun(cls, task, flowrun):
        return cls.objects(task=task, flowrun=flowrun).first()


#
#
# class Test(PrefectDocument):
#     _id = StringField(primary_key=True)
#     a=IntField()
#     b=IntField()
#     c=IntField()
#     d=IntField()
#     def __init__(self, a, b, **_mongo_kwargs):
#         id = str(a + b)
#         c = a + b
#         super().__init__(id=id, a=a, b=b, **_mongo_kwargs)
#
# class Test(Document):
#     _id = StringField(primary_key=True)
#     a=IntField()
#     b=IntField()
#
#     def __init__(self, a, b, **k):
#         super().__init__(a=a, b=b, **k)
#
#     @property
#     def id(self):
#         return str(self.a + self.b)
