import pytest
import pendulum as real_pendulum
import requests as real_requests
from prefect.utilities.imports import lazy_import


def test_lazy_import():
    pendulum = lazy_import("pendulum", globals())
    assert pendulum is not real_pendulum
    assert pendulum.datetime is real_pendulum.datetime


def test_lazy_import_alias():
    lazy_pendulum = lazy_import("pendulum", globals(), "lazy_pendulum")
    assert lazy_pendulum is not real_pendulum
    assert lazy_pendulum.datetime is real_pendulum.datetime


def test_lazy_import_submodule():
    lazy_requests = lazy_import("requests.utils", globals(), "lazy_requests")
    assert lazy_requests is not real_requests.utils
    assert lazy_requests.codecs is real_requests.utils.codecs


def test_lazy_import_with_bad_module():
    module = lazy_import("abcdefghijklmnop", globals())

    # error is not raised until we try to access module
    # use ImportError instead of ModuleNotFoundError for python 3.5 compat
    with pytest.raises(ImportError):
        dir(module)
