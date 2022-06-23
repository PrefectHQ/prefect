import pydantic
import pytest

from prefect.utilities.pydantic import PartialModel


class SimplePydantic(pydantic.BaseModel):
    x: int
    y: int


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
