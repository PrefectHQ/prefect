import packaging.requirements
import pydantic

from prefect.software.pip import PipRequirement, current_environment_requirements


class TestPipRequirement:
    def is_packaging_subclass(self):
        r = PipRequirement("prefect")
        assert isinstance(r, packaging.requirements.Requirement)

    def test_can_be_used_in_pydantic_model(self):
        class MyModel(pydantic.BaseModel):
            req: PipRequirement

        inst = MyModel(req="prefect")
        assert inst.req == PipRequirement("prefect")
        assert isinstance(inst.req, PipRequirement)

    def test_equality(self):
        assert PipRequirement("prefect") == PipRequirement("prefect")
        assert PipRequirement("prefect") != PipRequirement("prefect>=2")


# TODO: Add tests that mock the working set so we can make meaningful assertions


def test_current_environment_requirements():
    requirements = current_environment_requirements()
    assert all(isinstance(r, PipRequirement) for r in requirements)
    names = [r.name for r in requirements]
    assert len(names) == len(set(names)), "Names should not be repeated"


def test_current_environment_requirements_top_level_only():
    requirements = current_environment_requirements(exclude_nested=True)
    all_requirements = current_environment_requirements()
    assert {r.name for r in requirements}.issubset({r.name for r in all_requirements})
    assert len(requirements) < len(all_requirements)
    assert all(isinstance(r, PipRequirement) for r in requirements)
