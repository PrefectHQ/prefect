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
        models.FlowModel,
        models.TaskModel,
        models.EdgeModel,
        models.FlowRunModel,
        models.TaskRunModel,
    ]
    database.create_tables(tables)


class AESEncryptedField(peewee.BlobField):
    """
    Replacement for the Peewee playhouse AESEncryptedField until
    a Python3 bug is fixed.
    """

    def __init__(self, key, *args, **kwargs):
        self.key = key
        super(AESEncryptedField, self).__init__(*args, **kwargs)

    def get_cipher(self, key, iv):
        if len(key) > 32:
            raise ValueError('Key length cannot exceed 32 bytes.')
        # this line has the bugfix
        key = key + b' ' * (32 - len(key))
        return AES.new(key, AES.MODE_CFB, iv)

    def encrypt(self, value):
        iv = Random.get_random_bytes(AES.block_size)
        cipher = self.get_cipher(self.key, iv)
        return iv + cipher.encrypt(value)

    def decrypt(self, value):
        iv = value[:AES.block_size]
        cipher = self.get_cipher(self.key, iv)
        return cipher.decrypt(value[AES.block_size:])

    def db_value(self, value):
        if value is not None:
            return self.encrypt(value)

    def python_value(self, value):
        if value is not None:
            return self.decrypt(value)
