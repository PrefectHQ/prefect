import pendulum
import prefect
from prefect.utilities import database, serialize, state
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import reconstructor, relationship, backref
import ujson


class EncryptedStringType(sa.TypeDecorator):
    """
    A String column that automatically encrypts its contents.
    """
    impl = sa.String

    def __init__(self, encryption_key, *args, **kwargs):
        self.encryption_key = encryption_key
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        cipher = serialize.AESCipher(key=self.encryption_key)
        return cipher.encrypt(value)

    def process_result_value(self, value, dialect):
        cipher = serialize.AESCipher(key=self.encryption_key)
        return cipher.decrypt(value)


class SerializedType(sa.TypeDecorator):
    """
    A LargeBinary column that automatically serializes Python objects.

    NOTE: this column executes code when objects are serialized and
        deserialized (via the pickle module). Only trusted objects should
        be stored! To mitigate the risk slightly, serialized objects are
        encrypted prior to being stored in the database.
    """

    impl = sa.LargeBinary

    def __init__(self, encryption_key, *args, **kwargs):
        self.encryption_key = encryption_key
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        serialized = serialize.serialize(
            value, encryption_key=self.encryption_key)
        cipher = serialize.AESCipher(key=self.encryption_key)
        return cipher.encrypt(serialized)

    def process_result_value(self, value, dialect):
        cipher = serialize.AESCipher(key=self.encryption_key)
        serialized = cipher.decrypt(value)
        return serialize.deserialize(
            serialized, decryption_key=self.encryption_key)


class StateType(sa.TypeDecorator):
    """
    A String column that automatically takes its value from, and is read as,
    a State variable.
    """

    impl = sa.String

    def __init__(self, state_class, *args, **kwargs):
        self.state_class = state_class
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        """
        On the way in, store the string value of the state class's state
        """
        if isinstance(value, str):
            return value
        elif isinstance(value, self.state_class):
            return value.state
        else:
            raise TypeError(
                'Expected string or {}; received {}'.format(
                    self.state_class.__name__, type(value).__name__))

    def process_result_value(self, value, dialect):
        """
        On the way in, recreate the state variable from the integer state
        """
        return self.state_class(value)


class BaseModel:

    __abstract__ = True
    __repr_attrs__ = ['id']
    __repr_delimiter__ = '/'

    # -------------------------------------------------------------------------
    # id Column
    # -------------------------------------------------------------------------

    id = sa.Column(sa.Integer, primary_key=True)

    # -------------------------------------------------------------------------
    # Friendly __repr__
    # -------------------------------------------------------------------------

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, str(self))

    def __str__(self):
        attrs = [str(getattr(self, i)) for i in self.__repr_attrs__]
        return self.__repr_delimiter__.join(attrs)

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    @classmethod
    def _kwargs_to_where_clause(cls, **kwargs):
        where_clauses = []
        for key, value in kwargs.items():
            where_clauses.append(getattr(cls, key) == value)
        return where_clauses

    # -------------------------------------------------------------------------
    # CRUD methods
    # -------------------------------------------------------------------------

    def save(self):
        """
        Saves the current model to the database.
        """
        with database.transaction() as s:
            s.add(self)

    @classmethod
    def create(cls, **kwargs):
        """
        Creates and saves a new model.
        """
        model = cls()
        model.update(**kwargs)
        model.save()
        return model

    @classmethod
    def get_or_build(cls, **kwargs):
        """
        Attempts to retrieve the first model matching the provided filters,
        and builds it if it doesn't exist (but does not add it to the database).
        """
        with database.transaction() as s:
            count = (
                s.query(cls).filter(*cls._kwargs_to_where_clause(**kwargs))
                .count())
            if count == 1:
                return (
                    s.query(cls).filter(*cls._kwargs_to_where_clause(**kwargs))
                    .first())
            elif count > 1:
                raise ValueError(
                    'More than one model matches those critiera (found {})'.
                    format(count))
            else:
                return cls(**kwargs)

    @classmethod
    def get_or_create(cls, **kwargs):
        """
        Attempts to retrieve the first model matching the provided filters,
        and creates it if it doesn't exist.
        """
        model = cls.get_or_build(**kwargs)
        if not model.id:
            with database.transaction() as s:
                s.add(model)
        return model

    def update(self, **kwargs):
        """
        Updates the model with new attributes and saves it to the database
        """
        for key, value in kwargs.items():
            setattr(self, key, value)

    def delete(self):
        """
        Delete this model from the database.
        """
        with database.transaction() as s:
            s.delete(self)

    # -------------------------------------------------------------------------
    # Simple queries
    # -------------------------------------------------------------------------

    @classmethod
    def find(cls, id, error_if_missing=False):
        """
        Return the model corresponding to the provided id.

        Returns None if
        """
        if id is None:
            result = None
        else:
            with database.transaction() as s:
                result = s.query(cls).get(id)
        if error_if_missing and not result:
            raise ValueError(
                'No {} found with id {}'.format(type(cls).__name__, id))
        return result

    @classmethod
    def first(cls, *where_clauses, order_by=None, **kwargs):
        """
        Issues a select command with the provided filters and returns the first
        matching result.
        """
        where = list(where_clauses) + cls._kwargs_to_where_clause(**kwargs)

        with database.transaction() as s:
            return (
                s.query(cls)
                .filter(*where)
                .order_by(order_by)
                .first())  # yapf: disable

    @classmethod
    def where(cls, *where_clauses, **kwargs):
        """
        Issues a select command with the provided filters (implicity joined)
        by "AND").
        """
        where = list(where_clauses) + cls._kwargs_to_where_clause(**kwargs)
        with database.transaction() as s:
            return s.query(cls).filter(*where).all()

    @classmethod
    def count(cls, *where_clauses, **kwargs):
        """
        Issues a count(*) command with the provided filters (implicity joined)
        by "AND").
        """
        where = list(where_clauses) + cls._kwargs_to_where_clause(**kwargs)
        with database.transaction() as s:
            return s.query(cls).filter(*where).count()


Base = declarative_base(cls=BaseModel)


class Namespace(Base):
    __tablename__ = 'namespaces'
    __repr_attrs__ = ['name']

    name = sa.Column(sa.String, index=True, unique=True, nullable=False)
    flows = relationship('FlowModel', back_populates='namespace', cascade='all')


class FlowModel(Base):
    """
    Database model for a Prefect Flow
    """
    __tablename__ = 'flows'
    __repr_attrs__ = ['namespace', 'name', 'version']

    namespace_id = sa.Column(
        sa.Integer, sa.ForeignKey(Namespace.id), index=True)
    namespace = relationship(Namespace, back_populates='flows')
    name = sa.Column(sa.String, nullable=False, index=True)
    version = sa.Column(sa.String, nullable=False, index=True)

    # Active / inactive / archived
    state = sa.Column(
        StateType(state.FlowState),
        nullable=False,
        default=state.FlowState._default_state,
        index=True)

    # Serialized Flow
    serialized = sa.Column(
        SerializedType(
            encryption_key=prefect.config.get('db', 'encryption_key')),
        nullable=True)

    # tasks
    tasks = relationship('TaskModel', back_populates='flow', cascade='all')
    flow_runs = relationship(
        'FlowRunModel', back_populates='flow', cascade='all')

    __tableargs__ = (sa.UniqueConstraint(namespace_id, name, version),)


class TaskModel(Base):
    """
    Database model for a Prefect Task
    """
    __tablename__ = 'tasks'
    __repr_attrs__ = ['flow', 'name']

    flow_id = sa.Column(sa.ForeignKey(FlowModel.id), index=True)
    name = sa.Column(sa.String)

    flow = relationship(FlowModel, back_populates='tasks')
    task_runs = relationship(
        'TaskRunModel', back_populates='task', cascade='all')

    __tableargs__ = (sa.UniqueConstraint(name, flow_id),)


# class EdgeModel(Base):
#     """
#     Database model for a Prefect Edge
#     """
#     __tablename__ = 'edges'
#     upstream_task = pw.ForeignKeyField(TaskModel, related_name='downstream_tasks')
#     downstream_task = pw.ForeignKeyField(TaskModel, related_name='upstream_tasks')


class RunnerModel:

    created = sa.Column(sa.DateTime, default=pendulum.now)
    scheduled = sa.Column(sa.DateTime, nullable=True, index=True)
    started = sa.Column(sa.DateTime, nullable=True)
    finished = sa.Column(sa.DateTime, nullable=True)
    heartbeat = sa.Column(sa.DateTime, nullable=True)
    progress = sa.Column(sa.Float, default=0.0)
    state = sa.Column(sa.String, default='', index=True)


class FlowRunModel(Base, RunnerModel):
    """
    Database model for a Prefect FlowRun
    """

    __tablename__ = 'flow_runs'
    __repr_attrs__ = ['flow']

    state = sa.Column(
        StateType(state.FlowRunState),
        nullable=False,
        default=state.FlowRunState._default_state,
        index=True)

    flow_id = sa.Column(sa.ForeignKey(FlowModel.id), index=True)

    flow = relationship(FlowModel, back_populates='flow_runs')
    task_runs = relationship(
        'TaskRunModel',
        back_populates='flow_run',
        foreign_keys='TaskRunModel.flow_run_id',
        cascade='all')
    generating_task_run_id = sa.Column(
        sa.ForeignKey('task_runs.id'), index=True, nullable=True)
    generating_task_run = relationship(
        'TaskRunModel',
        back_populates='generated_flow_runs',
        foreign_keys=generating_task_run_id)


class TaskRunModel(Base, RunnerModel):
    """
    Database model for a Prefect TaskRun
    """
    __tablename__ = 'task_runs'
    __repr_attrs__ = ['task']

    state = sa.Column(
        StateType(state.TaskRunState),
        nullable=False,
        default=state.TaskRunState._default_state,
        index=True)
    flow_run_id = sa.Column(sa.ForeignKey(FlowRunModel.id), index=True)
    task_id = sa.Column(sa.ForeignKey(TaskModel.id), index=True)
    run_number = sa.Column(sa.Integer, default=1)

    generating_task_run_id = sa.Column(
        sa.ForeignKey('task_runs.id'), index=True, nullable=True)

    flow_run = relationship(
        FlowRunModel, back_populates='task_runs', foreign_keys=flow_run_id)
    flow = relationship(
        FlowModel,
        secondary=FlowRunModel.__table__,
        primaryjoin='TaskRunModel.flow_run_id == FlowRunModel.id',
        secondaryjoin='FlowRunModel.flow_id == FlowModel.id',
        viewonly=True)
    task = relationship(TaskModel, back_populates='task_runs')
    task_results = relationship(
        'TaskResultModel', back_populates='task_run', cascade='all')
    generated_task_runs = relationship(
        'TaskRunModel',
        backref=backref('generating_task_run', remote_side='TaskRunModel.id'),)
    generated_flow_runs = relationship(
        FlowRunModel,
        back_populates='generating_task_run',
        foreign_keys=FlowRunModel.generating_task_run_id,)

    __table_args__ = (sa.UniqueConstraint(flow_run_id, task_id, run_number),)


class TaskResultModel(Base):
    """
    Database model for the serialized result of a Prefect task
    """
    __tablename__ = 'task_results'
    __repr_attrs__ = ['task', 'index']

    task_run_id = sa.Column(sa.ForeignKey(TaskRunModel.id), index=True)
    index = sa.Column(sa.String)
    serialized = sa.Column(
        SerializedType(
            encryption_key=prefect.config.get('db', 'encryption_key')),
        nullable=True)

    task_run = relationship(
        TaskRunModel, back_populates='task_results', foreign_keys=[task_run_id])
    task = relationship(
        TaskModel,
        secondary=TaskRunModel.__table__,
        primaryjoin='TaskResultModel.task_run_id == TaskRunModel.id',
        secondaryjoin='TaskRunModel.task_id==TaskModel.id',
        viewonly=True,)

    __table_args__ = (sa.UniqueConstraint(task_run_id, index),)
