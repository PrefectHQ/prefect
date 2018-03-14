import random
import uuid

_id_rng = random.Random()
_id_rng.seed(prefect.config.general.get('id_seed', random.getrandbits(128)))


def generate_uuid():
    """
    Generates a random UUID4 using the global random seed.
    """
    return str(uuid.UUID(int=_id_rng.getrandbits(128)))
