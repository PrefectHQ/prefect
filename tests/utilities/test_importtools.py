from prefect.utilities.importtools import import_object


def test_import_object():
    rand = import_object("random")
    randint = import_object("random.randint")
    import random

    assert rand is random
    assert randint is random.randint
