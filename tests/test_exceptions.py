import cloudpickle
from pydantic import BaseModel, validator

from prefect.exceptions import (
    ParameterBindError,
    ParameterTypeError,
    SignatureMismatchError,
)


class ValidationTestModel(BaseModel):
    num: int
    string: str

    @validator("num")
    def must_be_int(cls, n):
        if not isinstance(n, int):
            raise TypeError("must be int")
        return n

    @validator("string")
    def must_be_str(cls, n):
        if not isinstance(n, str):
            raise TypeError("must be str")
        return n


class TestParameterTypeError:
    def test_construction_from_single_validation_error(self):
        expected_str = (
            "Flow run received invalid parameters:\n - num: value is not a valid"
            " integer"
        )
        try:
            ValidationTestModel(**{"num": "not an int", "string": "a string"})
        except Exception as exc:
            pte = ParameterTypeError.from_validation_error(exc)
            assert str(pte) == expected_str
            assert pte.args == ParameterTypeError(expected_str).args

    def test_construction_from_two_validation_errors(self):
        expected_str = (
            "Flow run received invalid parameters:\n - num: value is not a valid"
            " integer\n - string: str type expected"
        )
        try:
            ValidationTestModel(**{"num": "not an int", "string": [1, 2]})
        except Exception as exc:
            pte = ParameterTypeError.from_validation_error(exc)
            assert str(pte) == expected_str
            assert pte.args == ParameterTypeError(expected_str).args

    def test_pickle_roundtrip_single_error(self):
        try:
            ValidationTestModel(**{"num": "not an int", "string": "a string"})
        except Exception as exc:
            pte = ParameterTypeError.from_validation_error(exc)
            pickled = cloudpickle.dumps(pte)
            unpickled = cloudpickle.loads(pickled)
            assert str(pte) == str(unpickled)
            assert pte.args == unpickled.args

    def test_pickle_roundtrip_two_errors(self):
        try:
            ValidationTestModel(**{"num": "not an int", "string": [1, 2]})
        except Exception as exc:
            pte = ParameterTypeError.from_validation_error(exc)
            pickled = cloudpickle.dumps(pte)
            unpickled = cloudpickle.loads(pickled)
            assert str(pte) == str(unpickled)
            assert pte.args == unpickled.args


class TestParameterBindError:
    def test_construction_from_bind_error(self):
        def fn(a: int, b: str):
            pass

        type_error = TypeError("Demo TypeError")
        expected_str = (
            "Error binding parameters for function 'fn': Demo TypeError.\nFunction 'fn'"
            " has signature 'a: int, b: str' but received args: () and kwargs: {'c': 3,"
            " 'd': 'test'}."
        )
        pbe = ParameterBindError.from_bind_failure(
            fn, type_error, (), {"c": 3, "d": "test"}
        )
        assert str(pbe) == expected_str
        assert pbe.args == ParameterBindError(expected_str).args

    def test_pickle_roundtrip(self):
        def test_construction_from_bind_error(self):
            def fn(a: int, b: str):
                pass

            type_error = TypeError("Demo TypeError")
            expected_str = (
                "Error binding parameters for function 'fn': Demo TypeError.\nFunction"
                " 'fn' has signature 'a: int, b: str' but received args: () and kwargs:"
                " {'c': 3, 'd': 'test'}."
            )
            pbe = ParameterBindError.from_bind_failure(
                fn, type_error, (), {"c": 3, "d": "test"}
            )
            pickled = cloudpickle.dumps(pbe)
            unpickled = cloudpickle.loads(pickled)
            assert str(pbe) == str(unpickled)
            assert pbe.args == unpickled.args


class TestSignatureMismatchError:
    def test_from_bad_params(self):
        expected = (
            "Function expects parameters ['dog', 'cat'] but was provided with"
            " parameters ['puppy', 'kitty']"
        )
        sme = SignatureMismatchError.from_bad_params(["dog", "cat"], ["puppy", "kitty"])
        assert str(sme) == expected

    def test_pickle_roundtrip(self):
        sme = SignatureMismatchError.from_bad_params(["dog", "cat"], ["puppy", "kitty"])
        pickled = cloudpickle.dumps(sme)
        unpickled = cloudpickle.loads(pickled)
        assert str(sme) == str(unpickled)
        assert sme.args == unpickled.args
