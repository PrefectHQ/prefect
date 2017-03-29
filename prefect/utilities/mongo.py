import datetime
import inspect
import pymongo
import threading
import time


def save_or_reload(model):
    """
    Given a model with the primary key set, attempts to reload all
    values from the database. If the model isn't in the database, saves it
    as is.

    This is useful when initializing a model with an ORM analogue:

    def __init__(self, *args, **kwargs):
        self.orm = ORMModel(_id=orm_id)
        save_or_reload(model)

    If the model already exists, the ORM model is loaded with the latest
    information from the database. If it doesn't exist, it is created.
    """
    try:
        model.reload()
    except DoesNotExist:
        model.save()


class Heartbeat:

    def __init__(self, model, heartbeat_interval=1, heartbeat_key='heartbeat'):
        """
        Supplies a heartbeat for mongoengine models.

        The Heartbeat runs in a seperate thread and writes the current date
        to the model every `heartbeat_interval` seconds.
        """

        self.model = model
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_key = heartbeat_key
        self._stop = False

    def beat(self):
        while not self._stop:
            self.model._collection.update_one(
                {
                    '_id': self.model.id
                },
                {'$set': {
                    self.heartbeat_key: datetime.datetime.utcnow()
                }},)
            time.sleep(self.heartbeat_interval)

    def start(self):
        thread = threading.Thread(target=self.beat)
        thread.daemon = True
        thread.start()

    def stop(self):
        self._stop = True
