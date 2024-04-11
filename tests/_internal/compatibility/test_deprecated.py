from typing import Any, Dict, Optional

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    import pydantic.v1 as pydantic
else:
    import pydantic

import pytest

from prefect._internal.compatibility.deprecated import (
    DeprecatedInfraOverridesField,
    PrefectDeprecationWarning,
    deprecated_callable,
    deprecated_class,
    deprecated_field,
    deprecated_parameter,
    generate_deprecation_message,
)


def test_generate_deprecation_message():
    assert (
        generate_deprecation_message(
            "test name", start_date="Jan 2022", help="test help"
        )
        == "test name has been deprecated. It will not be available after Jul 2022."
        " test help"
    )


def test_generate_deprecation_message_when():
    assert (
        generate_deprecation_message(
            "test name", start_date="Jan 2022", help="test help", when="testing"
        )
        == "test name has been deprecated when testing. It will not be available after"
        " Jul 2022. test help"
    )


def test_generate_deprecation_message_invalid_start_date():
    with pytest.raises(ValueError, match="String does not match format MMM YYYY"):
        generate_deprecation_message("test name", start_date="2022")


def test_generate_deprecation_message_end_date():
    assert (
        generate_deprecation_message("test name", end_date="Dec 2023")
        == "test name has been deprecated. It will not be available after Dec 2023."
    )


def test_generate_deprecation_message_invalid_end_date():
    with pytest.raises(ValueError, match="String does not match format MMM YYYY"):
        generate_deprecation_message("test name", end_date="Foobar")


def test_generate_deprecation_message_no_start_or_end_date():
    with pytest.raises(
        ValueError, match="A start date is required if an end date is not provided"
    ):
        generate_deprecation_message("test name")


def test_deprecated_callable():
    @deprecated_callable(start_date="Jan 2022", help="test help")
    def foo():
        pass

    with pytest.warns(
        PrefectDeprecationWarning,
        match=(
            "test_deprecated.test_deprecated_callable.<locals>.foo has been deprecated."
            " It will not be available after Jul 2022. test help"
        ),
    ):
        foo()


def test_deprecated_parameter():
    @deprecated_parameter(name="y", start_date="Jan 2022", help="test help")
    def foo(
        x=None,
        y=None,
    ):
        pass

    # Does not warn
    foo(x=0)
    foo()

    with pytest.warns(
        PrefectDeprecationWarning,
        match=(
            "The parameter 'y' for 'foo' has been deprecated. It will not be available"
            " after Jul 2022. test help"
        ),
    ):
        foo(y=10)

    # positional
    with pytest.warns(PrefectDeprecationWarning):
        foo(0, 10)


def test_deprecated_parameter_when():
    @deprecated_parameter(
        name="x", when=lambda x: x > 5, start_date="Jan 2022", help="test help"
    )
    def foo(x: int = 0):
        pass

    # Does not warn
    foo(x=0)
    foo()

    with pytest.warns(
        PrefectDeprecationWarning,
        match=(
            "The parameter 'x' for 'foo' has been deprecated. It will not be available"
            " after Jul 2022. test help"
        ),
    ):
        foo(10)

    # positional
    with pytest.warns(PrefectDeprecationWarning):
        foo(10)

    # kwarg
    with pytest.warns(PrefectDeprecationWarning):
        foo(x=10)


def test_deprecated_field():
    @deprecated_field(name="y", start_date="Jan 2022", help="test help")
    class Foo(pydantic.BaseModel):
        x: Optional[int] = None
        y: Optional[int] = None

    # Does not warn
    Foo(x=0)
    Foo()

    with pytest.warns(
        PrefectDeprecationWarning,
        match=(
            "The field 'y' in 'Foo' has been deprecated. It will not be available after"
            " Jul 2022. test help"
        ),
    ):
        Foo(y=10)

    assert Foo.__fields__["y"].field_info.extra.get("deprecated") is True


def test_deprecated_field_when():
    @deprecated_field(
        name="x", when=lambda x: x > 5, start_date="Jan 2022", help="test help"
    )
    class Foo(pydantic.BaseModel):
        x: Optional[int] = None

    # Does not warn
    Foo(x=0)
    Foo()

    with pytest.warns(
        PrefectDeprecationWarning,
        match=(
            "The field 'x' in 'Foo' has been deprecated. It will not be available after"
            " Jul 2022. test help"
        ),
    ):
        Foo(x=10)


def test_deprecated_class():
    @deprecated_class(start_date="Jan 2022", help="test help")
    class MyClass:
        def __init__(self):
            pass

    with pytest.warns(
        PrefectDeprecationWarning,
        match=(
            "MyClass has been deprecated. It will not be available after Jul 2022."
            " test help"
        ),
    ):
        obj = MyClass()
        assert isinstance(obj, MyClass)


class TestDeprecatedInfraOverridesField:
    @pytest.fixture
    def my_deployment_model(self):
        class MyDeployment(DeprecatedInfraOverridesField, pydantic.BaseModel):
            name: str
            job_variables: Optional[Dict[str, Any]] = pydantic.Field(
                default_factory=dict,
                description="Overrides to apply to my deployment infrastructure at runtime.",
            )

        return MyDeployment

    @pytest.mark.parametrize(
        "job_variable_kwarg",
        [
            {"infra_overrides": {"foo": "bar"}},
            {"job_variables": {"foo": "bar"}},
        ],
    )
    def test_exposes_infra_overrides_as_job_variables(
        self, my_deployment_model, job_variable_kwarg
    ):
        deployment = my_deployment_model(name="test", **job_variable_kwarg)
        assert deployment.job_variables == {"foo": "bar"}
        assert deployment.infra_overrides == {"foo": "bar"}

        json = deployment.dict()
        assert json["infra_overrides"] == {"foo": "bar"}

    def test_infra_overrides_sets_job_variables(self, my_deployment_model):
        my_deployment = my_deployment_model(
            name="test",
            job_variables={"foo": "bar"},
        )
        assert my_deployment.job_variables == {"foo": "bar"}
        assert my_deployment.infra_overrides == {"foo": "bar"}

        my_deployment.infra_overrides = {"set_by": "infra_overrides"}
        assert my_deployment.job_variables == {"set_by": "infra_overrides"}
        assert my_deployment.infra_overrides == {"set_by": "infra_overrides"}

        json_dict = my_deployment.dict()
        assert json_dict["infra_overrides"] == {"set_by": "infra_overrides"}

    def test_job_variables_sets_infra_overrides(self, my_deployment_model):
        my_deployment = my_deployment_model(
            name="test",
            job_variables={"foo": "bar"},
        )
        assert my_deployment.job_variables == {"foo": "bar"}
        assert my_deployment.infra_overrides == {"foo": "bar"}

        my_deployment.job_variables = {"set_by": "job_variables"}
        assert my_deployment.job_variables == {"set_by": "job_variables"}
        assert my_deployment.infra_overrides == {"set_by": "job_variables"}

        json_dict = my_deployment.dict()
        assert json_dict["infra_overrides"] == {"set_by": "job_variables"}

    def test_job_variables_can_unset_infra_overrides(self, my_deployment_model):
        my_deployment = my_deployment_model(
            name="test",
            job_variables={"foo": "bar"},
        )
        assert my_deployment.job_variables == {"foo": "bar"}
        assert my_deployment.infra_overrides == {"foo": "bar"}

        my_deployment.job_variables = None
        assert my_deployment.job_variables is None
        assert my_deployment.infra_overrides is None

        json_dict = my_deployment.dict()
        assert json_dict["infra_overrides"] is None

    def test_infra_overrides_can_unset_job_variables(self, my_deployment_model):
        my_deployment = my_deployment_model(
            name="test",
            job_variables={"foo": "bar"},
        )
        assert my_deployment.job_variables == {"foo": "bar"}
        assert my_deployment.infra_overrides == {"foo": "bar"}

        my_deployment.infra_overrides = None
        assert my_deployment.job_variables is None
        assert my_deployment.infra_overrides is None

        json_dict = my_deployment.dict()
        assert json_dict["infra_overrides"] is None

    def test_job_variables_not_serialized(self, my_deployment_model):
        my_deployment = my_deployment_model(
            name="test",
            job_variables={"foo": "bar"},
        )
        assert my_deployment.job_variables == {"foo": "bar"}
        assert my_deployment.infra_overrides == {"foo": "bar"}

        json_dict = my_deployment.dict()
        assert "job_variables" not in json_dict
        assert json_dict["infra_overrides"] == {"foo": "bar"}

    def test_handles_setting_none(self, my_deployment_model):
        my_deployment = my_deployment_model(
            name="test",
        )
        my_deployment.infra_overrides = None
        my_deployment.job_variables = None

        json_dict = my_deployment.dict()
        assert "job_variables" not in json_dict
        assert json_dict["infra_overrides"] is None

    def test_does_not_override_description_if_none_set(self, my_deployment_model):
        assert "description" not in my_deployment_model.schema()

    def test_preserves_description_if_present(self):
        class MyModel(DeprecatedInfraOverridesField, pydantic.BaseModel):
            """Hey mom"""

            name: str
            job_variables: Optional[Dict[str, Any]] = pydantic.Field(
                default_factory=dict,
                description="Overrides to apply to my deployment infrastructure at runtime.",
            )

        assert MyModel.schema()["description"] == "Hey mom"
