import inspect
import pickle
import pytest
from prefect.tasks.toloka.utils import extract_id, structure_from_conf, with_logger
from toloka.client import Pool
from unittest.mock import Mock, patch


@pytest.fixture
def pool():
    return Pool(id='some_pool_id',
                project_id='some_project_id',
                type=Pool.Type.TRAINING)


class TestStructureFromConf:
    def test_object_given(self, pool):
        assert pool == structure_from_conf(pool, Pool)

    def test_dict_given(self, pool):
        assert pool == structure_from_conf(pool.unstructure(), Pool)

    def test_json_given(self, pool):
        assert pool == structure_from_conf(pool.to_json(), Pool)

    def test_pickle_given(self, pool):
        assert pool == structure_from_conf(pickle.dumps(pool), Pool)


class TestExtractId:
    def test_object_given(self, pool):
        assert pool.id == extract_id(pool, Pool)

    def test_dict_given(self, pool):
        assert pool.id == extract_id(pool.unstructure(), Pool)

    def test_json_given(self, pool):
        assert pool.id == extract_id(pool.to_json(), Pool)

    def test_id_given(self, pool):
        assert pool.id == extract_id(pool.id, Pool)

    def test_int_given(self):
        assert '123' == extract_id('123', Pool)

    def test_null_id_given(self, pool):
        pool.id = None
        with pytest.raises(ValueError, match='Got id=None'):
            extract_id(pool, Pool)


@patch('prefect.context')
def test_with_logger(context_mock, pool):
    logger_mock = Mock()
    context_get_mock = Mock(return_value=logger_mock)
    context_mock.get = context_get_mock

    @with_logger
    def some_func(arg, logger):
        logger.info(arg)

    func_params = inspect.signature(some_func).parameters
    assert {'arg': inspect.Parameter('arg', inspect.Parameter.POSITIONAL_OR_KEYWORD)} == func_params

    some_func('info-arg')

    assert 1 == len(logger_mock.mock_calls), logger_mock.mock_calls
    assert ('info-arg',) == logger_mock.mock_calls[0][1]
