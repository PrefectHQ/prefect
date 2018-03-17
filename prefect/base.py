import copy
import random
import uuid
from weakref import WeakValueDictionary

import prefect
from prefect.utilities.json import qualified_name

PREFECT_REGISTRY = WeakValueDictionary()

_id_rng = random.Random()
_id_rng.seed(prefect.config.general.get('id_seed') or random.getrandbits(128))


def generate_uuid():
    """
    Generates a random UUID using the _id_rng random seed.
    """
    return str(uuid.UUID(int=_id_rng.getrandbits(128)))

class PrefectObject:

    def __init__(self):
        self.id = generate_uuid()

    # Identification  ----------------------------------------------------------

    def __eq__(self, other):
        if type(self) == type(other):
            self_serialized = self.serialize()
            self_serialized.pop('id')
            other_serialized = other.serialize()
            other_serialized.pop('id')
            return self.serialized == other_serialized
        return False

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        self._id = str(value)
        self.register()

    @property
    def short_id(self):
        return self._id[:8]

    def register(self):
        if PREFECT_REGISTRY.get(self.id) not in (None, self):
            raise ValueError('ID {} is already registered!'.format(self.id))
        PREFECT_REGISTRY[self.id] = self

    # Misc ---------------------------------------------------------------------

    def copy(self):
        new = copy.copy(self)
        new.id = generate_uuid()
        return new

    def serialize(self):
        return dict(
            type=type(self).__name__,
            qualified_type=qualified_name(type(self)),
            id=self.id,
            prefect_version=prefect.__version__)

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.register()
