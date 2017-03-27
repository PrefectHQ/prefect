import croniter
import datetime
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


class FlowModel(Document):
    _id = StringField(primary_key=True)
    namespace = StringField(
        default=prefect.config.get('flows', 'default_namespace'))
    name = StringField(required=True, unique_with='namespace')
    version = StringField(default='1')
    schedule = EmbeddedDocumentField(Schedule)
    serialized = EmbeddedDocumentField(prefect.utilities.serialize.Serialized)
    active = BooleanField(
        default=prefect.config.getboolean('flows', 'default_active'))

    meta = {'collection': 'flowModels'}

    @queryset_manager
    def get_active(doc_cls, queryset):
        return [
            prefect.flow.Flow.from_serialized(**f['serialized'])
            for f in queryset.filter(active=True)
        ]

    # @queryset_manager
    # def scheduled(doc_cls, queryset):
    #     return queryset.filter(schedule)


class FlowRunModel(Document):
    _id = StringField(primary_key=True)
    flow = ReferenceField(FlowModel, required=True)
    # task_runs = MapField(ReferenceField('TaskRunModel'))
    state = StringField(default=State.PENDING, choices=list(State.all()))
    created = DateTimeField(default=lambda: datetime.datetime.now())
    started = DateTimeField()
    finished = DateTimeField()

    meta = {'collection': 'flowRuns', 'indexes': ['state', 'created']}


class TaskModel(Document):
    _id = StringField(primary_key=True)
    name = StringField(required=True, unique_with='flow')
    flow = ReferenceField(FlowModel, required=True)
    serialized = EmbeddedDocumentField(prefect.utilities.serialize.Serialized)

    meta = {'collection': 'taskModels', 'indexes': ['flow']}


class TaskRunModel(EmbeddedDocument):
    _id = StringField(primary_key=True)
    task = ReferenceField(TaskModel, required=True)
    flow_run = ReferenceField(FlowRunModel)
    state = StringField(default=State.NONE)
    run_count = IntField(default=0)
    scheduled_start = DateTimeField()
    created = DateTimeField(default=lambda: datetime.datetime.now())
    started = DateTimeField()
    finished = DateTimeField()

    meta = {
        'collection': 'taskRuns',
        'indexes': ['flow_run', 'state', 'scheduled_start']
    }

    @classmethod
    def from_task_and_flowrun(cls, task, flowrun):
        return cls.objects(task=task, flowrun=flowrun).first()
