import base64
import datetime
import distributed
import json
import peewee as pw
from playhouse import fields, kv

from prefect.configuration import config
import prefect.utilities.database as db


class PrefectModel(pw.Model):
    """
    Base class for Prefect PeeWee models
    """

    class Meta:
        database = db.database

    def __repr__(self):
        return '<{}({})>'.format(type(self).__name__, self.id)


class Namespace(PrefectModel):
    namespace = pw.CharField(index=True, unique=True)

    class Meta:
        db_table = 'namespaces'

    @classmethod
    def ensure_exists(cls, namespace):
        """
        Ensures that a namespace with the given name exists by creating it
        if it does not. Returns the Namespace.
        """
        if not cls.select().where(cls.namespace == namespace).exists():
            cls.create(namespace=namespace)
        return cls.get(cls.namespace == namespace)


class FlowModel(PrefectModel):
    """
    Database model for a Prefect Flow
    """
    namespace = pw.ForeignKeyField(Namespace, index=True, related_name='flows')
    name = pw.CharField(index=True)
    version = pw.CharField(
        default=config.get('flows', 'default_version'), index=True)
    active = pw.BooleanField(
        default=config.getboolean('flows', 'default_active'))
    archived = pw.BooleanField(default=False)
    serialized = pw.BlobField(null=True)

    # tasks = pw.Set

    class Meta:
        db_table = 'flows'
        indexes = (
            # unique index on namespace / name / version
            (('namespace', 'name', 'version'), True),)

    @classmethod
    def from_flow_id(cls, namespace, name, version, create_if_not_found=False):
        """
        Returns a FlowModel corresponding to the provided Flow parameters,
        if one exists in the database. If not, a new FlowModel is created
        (but not saved).
        """
        try:
            model = cls.get(
                (cls.namespace == Namespace.get(Namespace.namespace == namespace))
                & (cls.name == name)
                & (cls.version == version))  # yapf: disable
        except pw.DoesNotExist:
            if create_if_not_found:
                model = cls(namespace=Namespace.ensure_exists(namespace), name=name, version=version)
            else:
                raise
        return model

    def archive(self):
        self.archived = True
        self.save()

    # def delete_instance(self, delete_runs=False):
    #     """
    #     Deletes the FlowModel as well as any associated Tasks and
    #     Serialized values.
    #     """
    #     pass


class TaskModel(PrefectModel):
    """
    Database model for a Prefect Task
    """
    name = pw.CharField()
    flow = pw.ForeignKeyField(FlowModel, related_name='tasks', index=True)

    class Meta:
        db_table = 'tasks'
        indexes = (
            # unique index on name / flow
            (('name', 'flow'), True),)


class EdgeModel(PrefectModel):
    """
    Database model for a Prefect Edge
    """
    upstream_task = pw.ForeignKeyField(TaskModel, related_name='downstream_tasks')
    downstream_task = pw.ForeignKeyField(TaskModel, related_name='upstream_tasks')

    class Meta:
        db_table = 'edges'

deferred_taskrun = pw.DeferredRelation()


class FlowRunModel(PrefectModel):
    """
    Database model for a Prefect FlowRun
    """

    flow = pw.ForeignKeyField(FlowModel, related_name='flow_runs', index=True)

    created = pw.DateTimeField(default=datetime.datetime.now)
    scheduled_start = pw.DateTimeField(null=True, index=True)
    started = pw.DateTimeField(null=True)
    finished = pw.DateTimeField(null=True)
    heartbeat = pw.DateTimeField(null=True)

    progress = pw.FloatField(default=0)

    generated_by = pw.ForeignKeyField(
        deferred_taskrun, null=True, index=True, related_name='generated_flow_runs')

    state = pw.IntegerField(default=0, index=True)
    params = kv.JSONKeyStore(database=db.database)
    scheduled = pw.BooleanField(default=False)

    class Meta:
        db_table = 'flow_runs'


class TaskRunModel(PrefectModel):
    """
    Database model for a Prefect TaskRun
    """

    flowrun = pw.ForeignKeyField(
        FlowRunModel, related_name='task_runs', index=True)
    task = pw.ForeignKeyField(TaskModel, related_name='task_runs', index=True)
    run_number = fields.IntegerField(default=1, index=True)

    created = pw.DateTimeField(default=datetime.datetime.now)
    scheduled_start = pw.DateTimeField(null=True, index=True)
    started = pw.DateTimeField(null=True)
    finished = pw.DateTimeField(null=True)
    heartbeat = pw.DateTimeField(null=True)

    progress = pw.FloatField(default=0)

    generated_by = pw.ForeignKeyField(
        deferred_taskrun, null=True, index=True, related_name='generated_task_runs')

    state = pw.IntegerField(default=0, index=True)

    class Meta:
        db_table = 'task_runs'
        indexes = (
            # unique index on flowrun / task / run #
            (('flowrun', 'task', 'run_number'), True),)


deferred_taskrun.set_model(TaskRunModel)


class TaskResultModel(PrefectModel):
    """
    Database model for the serialized result of a Prefect task
    """
    taskrun = pw.ForeignKeyField(
        TaskRunModel, related_name='results', index=True)
    index = pw.CharField(index=True)
    serialized = pw.BlobField()

    class Meta:
        db_table = 'task_results'


# if the database is in memory, it needs to be initialized
# but if this script is being run directly, we don't want to run this code
# since it will have already run during the import of this module
if db.database.is_in_memory and not __name__ == '__main__':
    db.initialize()
