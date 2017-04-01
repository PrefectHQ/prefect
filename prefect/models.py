import peewee as pw
from playhouse import fields, kv

from prefect.configuration import config
import prefect.utilities.database as db


class PrefectModel(pw.Model):

    class Meta:
        database = db.database

    def __repr__(self):
        return '<{}({})>'.format(type(self).__name__, self.id)


class FlowModel(PrefectModel):
    name = pw.CharField(index=True)
    namespace = pw.CharField(
        default=config.get('flows', 'default_namespace'), index=True)
    version = pw.CharField(
        default=config.get('flows', 'default_version'), index=True)
    active = pw.BooleanField(
        default=config.getboolean('flows', 'default_active'))
    serialized = fields.AESEncryptedField(
        key=config.get('db', 'secret_key'), null=True)

    # tasks = pw.Set

    class Meta:
        db_table = 'flows'
        indexes = (
            # unique index on namespace / name / version
            (('namespace', 'name', 'version'), True),)


class TaskModel(PrefectModel):
    name = pw.CharField()
    flow = pw.ForeignKeyField(FlowModel, related_name='tasks', index=True)

    class Meta:
        db_table = 'tasks'
        indexes = (
            # unique index on name / flow
            (('name', 'flow'), True),)


class EdgeModel(PrefectModel):
    upstream_task = pw.ForeignKeyField(TaskModel, related_name='out_edges')
    downstream_task = pw.ForeignKeyField(TaskModel, related_name='in_edges')
    type = pw.CharField()

    class Meta:
        db_table = 'edges'


deferred_taskrun = pw.DeferredRelation()


class JobModel(PrefectModel):
    created = pw.DateTimeField()
    scheduled_start = pw.DateTimeField(null=True)
    started = pw.DateTimeField(null=True)
    finished = pw.DateTimeField(null=True)
    heartbeat = pw.DateTimeField(null=True)

    progress = pw.FloatField(default=0)

    generated_by = pw.ForeignKeyField(deferred_taskrun, null=True)

    state = pw.IntegerField(default=0)


class FlowRunModel(JobModel):

    flow = pw.ForeignKeyField(FlowModel, related_name='flowruns')
    params = kv.JSONKeyStore(database=db.database)
    scheduled = pw.BooleanField(default=False)

    class Meta:
        db_table = 'flowruns'


class TaskRunModel(JobModel):

    flowrun = pw.ForeignKeyField(FlowRunModel, related_name='taskruns')
    task = pw.ForeignKeyField(TaskModel, related_name='taskruns')
    run_number = fields.IntegerField(default=1)

    class Meta:
        db_table = 'taskruns'
        indexes = (
            # unique index on flowrun / task / run #
            (('flowrun', 'task', 'run_number'), True),)


deferred_taskrun.set_model(TaskRunModel)

# if the database is in memory, it needs to be initialized
# but if this script is being run directly, we don't want to run this code
# since it will have already run during the import of this module
if db.database.is_in_memory and not __name__ == '__main__':
    db.initialize()
