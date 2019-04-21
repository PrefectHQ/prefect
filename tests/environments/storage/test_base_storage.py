import pytest

import prefect
from prefect.environments.storage import Storage


def test_create_base_storage():
    with pytest.raises(TypeError):
        storage = Storage()
