import datetime
import pendulum
import threading
import time


class Heartbeat:

    def __init__(
            self,
            model,
            heartbeat_interval=1,
            heartbeat_column='heartbeat',):
        """
        Supplies a timestamp heartbeat for ORM models.

        The Heartbeat runs in a seperate thread and writes the current date
        to the model every `heartbeat_interval` seconds.

        model: PeeWee ORM Model
        heartbeat_interval: int
            The number of seconds to wait between heartbeats
        heartbeat_column: string
            The column of the model that will hold the heartbeat. Must be
            of type datetime.
        """

        self.model = model
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_column = heartbeat_column
        self._stop = False

    def beat(self):
        while not self._stop:
            setattr(self.model, self.heartbeat_column, pendulum.now())
            self.model.save()
            time.sleep(self.heartbeat_interval)

    def start(self):
        thread = threading.Thread(target=self.beat)
        thread.daemon = True
        thread.start()

    def stop(self):
        self._stop = True
