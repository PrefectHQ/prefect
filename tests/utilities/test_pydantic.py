import warnings
from pathlib import Path

import cloudpickle
import pytest
from pydantic import BaseModel, ConfigDict, Field

from prefect.utilities.dispatch import register_type
from prefect.utilities.pydantic import (
    PartialModel,
    add_cloudpickle_reduction,
    get_class_fields_only,
)

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    from prefect.utilities.pydantic import JsonPatch


class SimplePydantic(BaseModel):
    x: int
    y: int


REDUCTION_MODELS_EXC = None

try:
    # Capture exceptions to prevent errors from being thrown during collection
    # Models must be defined at the top-level to use the reduction decorator since it
    # imports types
    @add_cloudpickle_reduction
    class CythonFieldModel(BaseModel):
        x: Path  # The pydantic validator for 'Path' is compiled in cythonized builds

    @add_cloudpickle_reduction(exclude={"x"})
    class ReductionWithKwargs(BaseModel):
        x: int = 0
        y: str

except Exception as exc:
    REDUCTION_MODELS_EXC = exc


def test_register_type_without_known_base():
    class DispatchlessBase(BaseModel):
        pass

    with pytest.raises(ValueError, match="No registry found for type 'Foo'"):

        @register_type
        class Foo(DispatchlessBase):
            pass


class TestCloudpickleReduction:
    @pytest.fixture(autouse=True)
    def check_for_model_decoration_exception(self):
        if REDUCTION_MODELS_EXC:
            raise RuntimeError("Failed to create test model.") from REDUCTION_MODELS_EXC

    def test_add_cloudpickle_reduction(self):
        model = CythonFieldModel(x="./foo.txt")
        result = cloudpickle.loads(cloudpickle.dumps(model))
        assert result == model

    def test_add_cloudpickle_reduction_with_kwargs(self):
        model = ReductionWithKwargs(x=1, y="test")

        # A mock is hard to use here because it is not serializable so we exclude a
        # field instead
        result = cloudpickle.loads(cloudpickle.dumps(model))

        assert result.x == 0, (
            "'x' should return to the default value since it was excluded"
        )
        assert result.y == "test"


class TestGetSubclassFieldsOnly:
    def test_get_subclass_fields(self):
        class ParentModel(BaseModel):
            parent_field: str = ""

        class ChildModel(ParentModel):
            child_field: str = ""

        res = get_class_fields_only(ChildModel)
        assert res == {"child_field"}

    def test_get_subclass_fields_with_redefined_field(self):
        class ParentModel(BaseModel):
            parent_field: str = ""
            redefined_field: str = ""

        class ChildModel(ParentModel):
            child_field: str = ""
            redefined_field: str = ""

        res = get_class_fields_only(ChildModel)
        assert res == {"child_field", "redefined_field"}

    def test_get_subclass_fields_with_multiple_inheritance(self):
        class ParentModel1(BaseModel):
            parent_field1: str = ""

        class ParentModel2(BaseModel):
            parent_field2: str = ""

        class ChildModel(ParentModel1, ParentModel2):
            child_field: str = ""

        res = get_class_fields_only(ChildModel)
        assert res == {"child_field"}

    def test_get_subclass_fields_with_multiple_parents(self):
        class ParentModel1(BaseModel):
            parent_field1: str = ""

        class ParentModel2(ParentModel1):
            parent_field2: str = ""

        class ChildModel(ParentModel2):
            child_field: str = ""

        res = get_class_fields_only(ChildModel)
        assert res == {"child_field"}


class TestPartialModel:
    def test_init(self):
        p = PartialModel(SimplePydantic)
        assert p.model_cls == SimplePydantic
        assert p.fields == {}

    def test_init_with_fields(self):
        p = PartialModel(SimplePydantic, x=1, y=2)
        assert p.fields == {"x": 1, "y": 2}
        m = p.finalize()
        assert isinstance(m, SimplePydantic)
        assert m == SimplePydantic(x=1, y=2)

    def test_repr(self):
        p = PartialModel(SimplePydantic, x=1, y=2)
        assert repr(p) == "PartialModel(cls=SimplePydantic, x=1, y=2)"

    def test_init_with_invalid_field(self):
        with pytest.raises(ValueError, match="Field 'z' is not present in the model"):
            PartialModel(SimplePydantic, x=1, z=2)

    def test_set_attribute(self):
        p = PartialModel(SimplePydantic)
        p.x = 1
        p.y = 2
        assert p.finalize() == SimplePydantic(x=1, y=2)

    def test_set_invalid_attribute(self):
        p = PartialModel(SimplePydantic)
        with pytest.raises(ValueError, match="Field 'z' is not present in the model"):
            p.z = 1

    def test_set_already_set_attribute(self):
        p = PartialModel(SimplePydantic, x=1)
        with pytest.raises(ValueError, match="Field 'x' has already been set"):
            p.x = 2

    def test_finalize_with_fields(self):
        p = PartialModel(SimplePydantic)
        m = p.finalize(x=1, y=2)
        assert isinstance(m, SimplePydantic)
        assert m == SimplePydantic(x=1, y=2)

    def test_finalize_with_invalid_field(self):
        p = PartialModel(SimplePydantic)
        with pytest.raises(ValueError, match="Field 'z' is not present in the model"):
            p.finalize(z=1)

    def test_finalize_with_already_set_field(self):
        p = PartialModel(SimplePydantic, x=1)
        with pytest.raises(ValueError, match="Field 'x' has already been set"):
            p.finalize(x=1)

    def test_finalize_with_missing_field(self):
        p = PartialModel(SimplePydantic, x=1)
        with pytest.raises(ValueError, match="validation error"):
            p.finalize()


class TestJsonPatch:
    def test_json_schema(self):
        class PatchModel(BaseModel):
            model_config = ConfigDict(arbitrary_types_allowed=True)

            patch: JsonPatch = Field(default_factory=lambda: JsonPatch([]))

        schema = PatchModel.model_json_schema()

        assert schema["properties"]["patch"] == {
            "title": "Patch",
            "type": "array",
            "format": "rfc6902",
            "items": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
        }
