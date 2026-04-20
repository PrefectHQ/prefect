import shutil
from pathlib import Path

import pytest
from yamllint import linter
from yamllint.config import YamlLintConfig

import prefect
from prefect.deployments.base import (
    configure_project_by_recipe,
    create_default_prefect_yaml,
    initialize_project,
)
from prefect.utilities.filesystem import tmpchdir

TEST_PROJECTS_DIR = prefect.__development_base_path__ / "tests" / "test-projects"

RECIPES_DIR = (
    prefect.__development_base_path__ / "src" / "prefect" / "deployments" / "recipes"
)

TEMPLATES_DIR = (
    prefect.__development_base_path__ / "src" / "prefect" / "deployments" / "templates"
)

# yamllint configuration for static template and recipe files: extends default
# rules with relaxed indentation to accept both indented and non-indented
# sequence styles, since Python's yaml.dump() does not indent list items by
# default.
YAMLLINT_CONFIG = YamlLintConfig(
    """\
extends: default
rules:
  indentation:
    indent-sequences: whatever
"""
)

# yamllint configuration for generated files: same as above but with
# line-length disabled, because generated files may contain user-provided
# values (e.g. directory paths) that can exceed 80 characters.
YAMLLINT_GENERATED_CONFIG = YamlLintConfig(
    """\
extends: default
rules:
  indentation:
    indent-sequences: whatever
  line-length: disable
"""
)


def _assert_yamllint_passes(
    content: str,
    filepath: str = "<string>",
    config: YamlLintConfig = YAMLLINT_CONFIG,
) -> None:
    """Assert that the given YAML content passes yamllint with no errors
    or warnings."""
    problems = list(linter.run(content, config))
    if problems:
        details = "\n".join(
            f"  line {p.line}: [{p.level}] {p.message} ({p.rule})" for p in problems
        )
        pytest.fail(f"yamllint found issues in {filepath}:\n{details}")


@pytest.fixture(autouse=True)
def project_dir(tmp_path):
    with tmpchdir(tmp_path):
        shutil.copytree(TEST_PROJECTS_DIR, tmp_path, dirs_exist_ok=True)
        (tmp_path / ".prefect").mkdir(exist_ok=True, mode=0o0700)
        yield tmp_path


class TestStaticYamlFilesPassYamllint:
    """Validate that all static YAML files (recipes and templates) conform
    to yamllint standards."""

    @pytest.mark.parametrize(
        "recipe",
        [d.name for d in sorted(RECIPES_DIR.iterdir()) if d.is_dir()],
    )
    def test_recipe_yaml_passes_yamllint(self, recipe):
        yaml_path = RECIPES_DIR / recipe / "prefect.yaml"
        content = yaml_path.read_text()
        _assert_yamllint_passes(content, filepath=str(yaml_path))

    @pytest.mark.parametrize(
        "template",
        [f.name for f in sorted(TEMPLATES_DIR.glob("*.yaml"))],
    )
    def test_template_yaml_passes_yamllint(self, template):
        yaml_path = TEMPLATES_DIR / template
        content = yaml_path.read_text()
        _assert_yamllint_passes(content, filepath=str(yaml_path))


class TestGeneratedYamlPassesYamllint:
    """Validate that generated prefect.yaml files conform to yamllint
    standards.

    Uses a relaxed line-length config because generated files contain
    user-provided values (e.g. directory paths from the current working
    directory) that may exceed 80 characters depending on the environment.
    """

    def test_default_generated_yaml_passes_yamllint(self):
        contents = configure_project_by_recipe(
            "local", directory="/tmp/test", name="test"
        )
        create_default_prefect_yaml(".", name="test-project", contents=contents)

        generated = Path("prefect.yaml").read_text()
        _assert_yamllint_passes(
            generated,
            filepath="generated prefect.yaml (local)",
            config=YAMLLINT_GENERATED_CONFIG,
        )

    @pytest.mark.parametrize(
        "recipe",
        [d.name for d in sorted(RECIPES_DIR.iterdir()) if d.is_dir()],
    )
    def test_initialized_project_yaml_passes_yamllint(self, recipe):
        files = initialize_project(name="test-project", recipe=recipe)

        if "prefect.yaml" in files:
            generated = Path("prefect.yaml").read_text()
            _assert_yamllint_passes(
                generated,
                filepath=f"generated prefect.yaml ({recipe})",
                config=YAMLLINT_GENERATED_CONFIG,
            )
