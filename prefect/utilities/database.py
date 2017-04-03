from Crypto.Cipher import AES
from Crypto import Random
import peewee
from playhouse import db_url
from prefect import config, models


def connect(connection_url=None):
    """
    Connect to the Prefect database.
    """
    if connection_url is None:
        connection_url = config.get('db', 'connection_url')
    in_memory_dbs = ('', 'sqlite://', 'sqlite://:memory:', ':memory:')
    if connection_url in in_memory_dbs:
        connection_url = 'sqlite://'
    database = db_url.connect(connection_url)
    if connection_url == 'sqlite://':
        database.is_in_memory = True
    return database


database = connect()


def initialize():
    """
    Initialize the Prefect database:
        - create tables
        - create indices / constraints
        - create relationships
    """
    tables = [
        models.Namespace,
        models.FlowModel,
        models.TaskModel,
        models.EdgeModel,
        models.FlowRunModel,
        models.TaskRunModel,
        models.TaskResultModel,
    ]
    database.create_tables(tables)
