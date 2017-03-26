import croniter
import datetime
import itertools
from mongoengine import Document, EmbeddedDocument
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


class SerializedFlow(EmbeddedDocument):
    header = DictField()
    frames = ListField(StringField(), required=True)


class Flow(Document):
    _id = StringField(primary_key=True)
    name = StringField(required=True, unique_with='namespace')
    namespace = StringField(
        default=prefect.config.get('flows', 'default_namespace'))
    version = StringField(default='1')
    schedule = ReferenceField(Schedule)
    serialized_flow = EmbeddedDocumentField(SerializedFlow)
    active = BooleanField(
        default=prefect.config.getboolean('flows', 'default_active'))
    meta = {'collection': 'flows'}


class FlowRun(Document):
    flow = ReferenceField(Flow, required=True)
    state = StringField(default=State.PENDING)
    start = DateTimeField()
    end = DateTimeField()
    meta = {'collection': 'flowruns'}


class Task(Document):
    name = StringField(required=True, unique_with='flow')
    flow = ReferenceField(Flow, required=True)
    meta = {'collection': 'tasks'}


class TaskRun(Document):
    task = ReferenceField(Task, required=True)
    run = ReferenceField(FlowRun, unique_with='task')
    state = StringField(default=State.PENDING)
    attempt = IntField(default=0)
    scheduled = DateTimeField()
    meta = {'collection': 'taskruns'}
