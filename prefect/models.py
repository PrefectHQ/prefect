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


class SerializedFlow(EmbeddedDocument):
    header = DictField()
    frames = ListField(StringField(), required=True)


class Flows(Document):
    _id = StringField(primary_key=True)
    name = StringField(required=True, unique_with='namespace')
    namespace = StringField(
        default=prefect.config.get('flows', 'default_namespace'))
    version = StringField(default='1')
    schedule = EmbeddedDocumentField(Schedule)
    serialized_flow = EmbeddedDocumentField(SerializedFlow)
    active = BooleanField(
        default=prefect.config.getboolean('flows', 'default_active'))


    @queryset_manager
    def get_active(doc_cls, queryset):
        return [
            prefect.flow.Flow.from_serialized(**f['serialized_flow'])
            for f in queryset.filter(active=True)]



    # @queryset_manager
    # def scheduled(doc_cls, queryset):
    #     return queryset.filter(schedule)



class FlowRuns(Document):
    flow = ReferenceField(Flows, required=True)
    state = StringField(default=State.PENDING)
    start = DateTimeField()
    end = DateTimeField()


class Tasks(Document):
    name = StringField(required=True, unique_with='flow')
    flow = ReferenceField(Flows, required=True)


class TaskRuns(Document):
    task = ReferenceField(Tasks, required=True)
    run = ReferenceField(FlowRuns, unique_with='task')
    state = StringField(default=State.PENDING)
    attempt = IntField(default=0)
    scheduled = DateTimeField()
