import os
import uuid
import pytest
import threading
import pickle
from collections import defaultdict

import cloudpickle

from prefect.utilities.local_cache import (
    shared_object,
    clear_local_cache,
    clear_all_local_caches,
    _SerializableLock,
)
from prefect import Flow, task


@pytest.fixture(autouse=True)
def ensure_cleared_caches():
    yield
    clear_all_local_caches()


@shared_object
def temporary_file(directory):
    pid = os.getpid()
    uid = uuid.uuid4().hex
    path = os.path.join(directory, f"{uid}-{pid}")
    with open(path, "w"):
        pass
    yield path
    os.unlink(path)


@task
def get_temporary_file(directory):
    path = temporary_file(directory)
    assert os.path.exists(path)
    return path


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_shared_object_with_executors(executor, tmpdir):
    directory = str(tmpdir)
    with Flow("test") as flow:
        results = get_temporary_file.map([directory] * 100)

    state = flow.run(executor=executor)
    paths = state.result[results].result

    by_pid = defaultdict(set)
    for p in paths:
        by_pid[p.rsplit("-", 1)[1]].add(p)

    # no process created ran `temporary_file` more than once
    for pid, paths in by_pid.items():
        assert len(paths) == 1

    # after __exit__, all temporary files were removed
    assert not os.listdir(directory)


def test_error_in_shared_object_teardown_is_logged(caplog):
    @shared_object
    def test():
        yield 1
        raise ValueError("failed to cleanup")

    a = test()
    assert a == 1

    clear_all_local_caches()
    assert any("shared_object" in rec.message for rec in caplog.records)
    assert any(str(rec.exc_info[1]) == "failed to cleanup" for rec in caplog.records)


def test_shared_object_called_outside_flow_run(tmpdir):
    directory = str(tmpdir)
    fil = temporary_file(directory)
    assert os.path.exists(fil)
    clear_all_local_caches()
    assert not os.path.exists(fil)


def test_shared_object_functions_are_cloudpickleable():
    @shared_object
    def test(a):
        return object()

    test2 = cloudpickle.loads(cloudpickle.dumps(test))

    assert test(1) is test2(1)
    assert test(2) is test2(2)
    assert test(3) is not test2(4)


def test_shared_object_caches_by_key():
    @shared_object
    def test(a, b=2):
        return (a, b)

    # args are passed through properly
    assert test(1) == (1, 2)
    assert test(a=1) == (1, 2)
    assert test(1, 3) == (1, 3)
    assert test(1, b=3) == (1, 3)
    assert test(a=1, b=3) == (1, 3)

    # args only
    assert test(1) is test(1)
    assert test(2) is test(2)
    assert test(1) is not test(2)
    assert test(a=1) is test(1)

    # args and kwargs
    assert test(2, 2) is test(2)
    assert test(2, 3) is not test(2)
    assert test(2, 3) is test(2, 3)
    assert test(2, 3) is test(2, b=3)
    assert test(1, b=2) is not test(1, b=3)
    assert test(1, b=2) is not test(2, b=2)


def test_shared_object_unhashable_args_errors():
    @shared_object
    def test(a):
        pass

    with pytest.raises(TypeError) as exc:
        test([1, 2, 3])

    assert "shared_object" in str(exc.value)
    assert "hashable" in str(exc.value)


def test_shared_object_custom_key_function():
    key_args = None

    def key(a, b):
        nonlocal key_args
        key_args = (a, b)
        return (tuple(a), b)

    @shared_object(key=key)
    def test(a, b=1):
        return (a, b)

    a = test([1, 2, 3])
    assert key_args == ([1, 2, 3], 1)
    assert a is test([1, 2, 3])
    assert a is test([1, 2, 3], b=1)

    assert a is not test([1, 2, 3], 2)
    assert key_args == ([1, 2, 3], 2)

    assert a is not test([1, 2, 3], b=3)
    assert key_args == ([1, 2, 3], 3)

    assert test([1, 2, 3], 2) is test([1, 2, 3], 2)
    assert test([1, 2, 3], b=3) is test([1, 2, 3], 3)
    assert a is not test([1, 2])


def test_clear_local_cache_doesnt_error_if_missing():
    clear_local_cache("invalid")


@pytest.mark.parametrize("reentrant", [False, True])
def test_SerializableLock_creation(reentrant):
    # the lock "types" in threading are actually functions, we need to retrieve
    # the type at runtime
    lock_type = type(threading.RLock()) if reentrant else type(threading.Lock())
    a = _SerializableLock(reentrant=reentrant)
    b = _SerializableLock(reentrant=reentrant)
    assert a.lock is not b.lock
    assert a.token != b.token
    assert a.reentrant == b.reentrant == reentrant
    assert type(a.lock) is lock_type
    assert type(b.lock) is lock_type

    # unpickling in a process where a lock already exists with that token uses
    # the same lock
    a2 = pickle.loads(pickle.dumps(a))
    assert a2.lock is a.lock

    # unpickling in a process where a lock doesn't exist creates with same
    # parameters
    b_token = b.token
    s = pickle.dumps(b)
    del b
    assert b_token not in _SerializableLock._locks
    b2 = pickle.loads(s)
    assert b2.reentrant == reentrant
    assert b2.token == b_token
    assert type(b2.lock) is lock_type


@pytest.mark.parametrize("reentrant", [False, True])
def test_SerializableLock_usage(reentrant):
    a = _SerializableLock(reentrant=reentrant)

    with a:
        if reentrant:
            # reentrant locks can be re-entered
            with a:
                pass

    assert a.token in repr(a)
