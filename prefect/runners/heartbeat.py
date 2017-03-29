import datetime
import threading
import time

class Heartbeat:

    def __init__(self, model, heartbeat_interval=1, heartbeat_key='heartbeat'):
        """
        Supplies a timestamp heartbeat for mongoengine models.

        The Heartbeat runs in a seperate thread and writes the current date
        to the model every `heartbeat_interval` seconds.

        model: MongoEngine Document
        heartbeat_interval: int
            The number of seconds to wait between heartbeats
        heartbeat_key: string
            The key of the Document that will hold the heartbeat.
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
