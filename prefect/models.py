import datetime
import inspect
import itertools
from mongoengine import Document, EmbeddedDocument, queryset_manager, fields
import prefect
from prefect.state import State
from prefect.utilities.serialize import Serialized


class TaskModel(Document):
    _id = fields.StringField(primary_key=True)
    name = fields.StringField(required=True, unique_with='flow_id')
    flow_id = fields.StringField(required=True)
    type = fields.StringField()
    max_retries = fields.IntField()

    meta = {'collection': 'taskModels', 'indexes': ['flow_id']}


class FlowModel(Document):
    _id = fields.StringField(primary_key=True)
    namespace = fields.StringField(
        default=prefect.config.get('flows', 'default_namespace'))
    name = fields.StringField(required=True, unique_with='namespace')
    version = fields.StringField(default='1')
    required_params = fields.ListField(fields.StringField, default=tuple())
    active = fields.BooleanField(
        default=prefect.config.getboolean('flows', 'default_active'))
    serialized = fields.EmbeddedDocumentField(Serialized)
    graph = fields.MapField(
        fields.ListField(fields.StringField(), default=tuple()))
    tasks = fields.MapField(fields.ReferenceField(TaskModel))

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


class FlowRunModel(Document):
    _id = fields.StringField(primary_key=True)
    flow = fields.ReferenceField(FlowModel, required=True)
    params = fields.MapField(
        fields.EmbeddedDocumentField(Serialized), default=lambda: dict())
    generated_by = fields.ReferenceField('TaskRunModel')
    state = fields.StringField(
        default=State.PENDING, choices=list(State.all_states()))

    scheduled_start = fields.DateTimeField()
    created = fields.DateTimeField(default=lambda: datetime.datetime.utcnow())
    started = fields.DateTimeField()
    finished = fields.DateTimeField()
    heartbeat = fields.DateTimeField()

    meta = {
        'collection': 'flowRuns',
        'indexes': [
            'state',
            'created',
            'flow',
            'generated_by',
            'scheduled_start',
        ]
    }


class TaskRunModel(Document):
    _id = fields.StringField(primary_key=True)

    task = fields.ReferenceField(TaskModel, required=True)
    run_id = fields.StringField(required=True)
    state = fields.StringField(default=State.NONE)
    run_number = fields.IntField(default=1)

    scheduled_start = fields.DateTimeField()

    created = fields.DateTimeField(default=lambda: datetime.datetime.utcnow())
    started = fields.DateTimeField()
    finished = fields.DateTimeField()
    heartbeat = fields.DateTimeField()

    meta = {
        'collection': 'taskRuns',
        'indexes': ['task', 'run_id', 'state', 'scheduled_start']
    }

    @classmethod
    def from_task_and_flowrun(cls, task, flowrun):
        return cls.objects(task=task, flowrun=flowrun).first()
