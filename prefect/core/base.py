import uuid


class PrefectObject:

    def __init__(self, id=None):
        self.id = id

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        if value is None:
            value = uuid.uuid4()
        elif not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        self._id = str(value)
