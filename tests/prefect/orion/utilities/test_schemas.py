import pytest
import pydantic
from prefect.orion.utilities.schemas import subclass_model


class TestSubclassModel:
    class Parent(pydantic.BaseModel):
        class Config:
            extra = "forbid"

        x: int
        y: int = 2

    def test_subclass_is_a_subclass(self):
        Child = subclass_model(self.Parent)
        assert issubclass(Child, self.Parent)

    def test_parent_is_unchanged(self):
        original_fields = self.Parent.__fields__.copy()
        Child = subclass_model(self.Parent)
        assert self.Parent.__fields__ == original_fields

    def test_default_subclass_name(self):
        Child = subclass_model(self.Parent)
        assert Child.__name__ == "Parent"

    def test_subclass_name(self):
        Child = subclass_model(self.Parent, name="Child")
        assert Child.__name__ == "Child"

    def test_subclass_fields(self):
        Child = subclass_model(self.Parent, name="Child")
        c = Child(x=1)
        assert c.x == 1
        assert c.y == 2

    def test_subclass_include(self):
        Child = subclass_model(self.Parent, name="Child", include=["y"])
        c = Child(y=1)
        assert c.y == 1
        assert not hasattr(c, "x")

    def test_subclass_exclude(self):
        Child = subclass_model(self.Parent, name="Child", exclude=["x"])
        c = Child(y=1)
        assert c.y == 1
        assert not hasattr(c, "x")

    def test_extend_subclass(self):
        class Child(subclass_model(self.Parent, include=["y"])):
            z: int

        c = Child(y=5, z=10)
        assert c.y == 5
        assert c.z == 10

    def test_extend_subclass_respects_config(self):
        class Child(subclass_model(self.Parent, include=["y"])):
            z: int

        with pytest.raises(
            pydantic.ValidationError, match="(extra fields not permitted)"
        ):
            Child(y=5, z=10, q=17)
