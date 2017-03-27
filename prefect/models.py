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
    ReferenceField,
    StringField,)
import prefect
from prefect.state import State
from prefect.utilities.schedules import Schedule


class FlowModel(Document):
    _id = StringField(primary_key=True)
    name = StringField(required=True, unique_with='namespace')
    namespace = StringField(
        default=prefect.config.get('flows', 'default_namespace'))
    version = StringField(default='1')
    schedule = EmbeddedDocumentField(Schedule)
    serialized = EmbeddedDocumentField(prefect.utilities.serialize.SerializedFlow)
    active = BooleanField(
        default=prefect.config.getboolean('flows', 'default_active'))

    meta = {'collection': 'flowModels'}

    @queryset_manager
    def get_active(doc_cls, queryset):
        return [
            prefect.flow.Flow.from_serialized(**f['serialized_flow'])
            for f in queryset.filter(active=True)
        ]

    # @queryset_manager
    # def scheduled(doc_cls, queryset):
    #     return queryset.filter(schedule)


class FlowRun(Document):
    _id = StringField(primary_key=True)
    flow = ReferenceField(FlowModel, required=True)
    state = StringField(default=State.PENDING, choices=list(State.all()))
    created = DateTimeField(default=lambda: datetime.datetime.now())
    started = DateTimeField()
    finished = DateTimeField()

    meta = {'collection': 'flowRuns'}


class TaskModel(Document):
    _id = StringField(primary_key=True)
    name = StringField(required=True, unique_with='flow')
    flow = ReferenceField(FlowModel, required=True)

    meta = {'collection': 'taskModels'}


class TaskRun(Document):
    task = ReferenceField(TaskModel, required=True)
    flowrun = ReferenceField(FlowRun, unique_with='task')
    state = StringField(default=State.PENDING)
    attempt = IntField(default=0)
    scheduled = DateTimeField()

    meta = {'collection': 'taskRuns'}

    @classmethod
    def from_task_and_flowrun(cls, task, flowrun):
        return cls.objects(task=task, flowrun=flowrun).first()
