import shutil
from pathlib import Path

import pytest

yamllint = pytest.importorskip("yamllint", reason="yamllint is not installed")
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
    "extends: default\nrules:\n  indentation:\n    indent-sequences: whatever\n"
)

# yamllint configuration for generated files: same as above but with
# line-length disabled, because generated files may contain user-provided
# values (e.g. directory paths) that can exceed 80 characters.
YAMLLINT_GENERATED_CONFIG = YamlLintConfig(
    "extends: default\n"
    "rules:\n"
    "  indentation:\n"
    "    indent-sequences: whatever\n"
    "  line-length: disable\n"
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


class TestRecipeYamlFilesPassYamllint:
    """Validate that all recipe YAML files conform to yamllint standards."""

    @pytest.mark.parametrize(
        "recipe",
        [d.name for d in sorted(RECIPES_DIR.iterdir()) if d.is_dir()],
    )
    def test_recipe_yaml_passes_yamllint(self, recipe):
        yaml_path = RECIPES_DIR / recipe / "prefect.yaml"
        content = yaml_path.read_text()
        _assert_yamllint_passes(content, filepath=str(yaml_path))


class TestTemplateYamlFilesPassYamllint:
    """Validate that all template YAML files conform to yamllint standards."""

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


class TestYamlLintRules:
    """Validate specific yamllint rules that the PR addresses."""

    @pytest.mark.parametrize(
        "recipe",
        [d.name for d in sorted(RECIPES_DIR.iterdir()) if d.is_dir()],
    )
    def test_recipe_has_document_start_marker(self, recipe):
        yaml_path = RECIPES_DIR / recipe / "prefect.yaml"
        content = yaml_path.read_text()
        assert content.startswith("---"), (
            f"{yaml_path} is missing the '---' document start marker"
        )

    def test_template_has_document_start_marker(self):
        yaml_path = TEMPLATES_DIR / "prefect.yaml"
        content = yaml_path.read_text()
        assert content.startswith("---"), (
            f"{yaml_path} is missing the '---' document start marker"
        )

    @pytest.mark.parametrize(
        "recipe",
        [d.name for d in sorted(RECIPES_DIR.iterdir()) if d.is_dir()],
    )
    def test_recipe_no_lines_exceed_80_chars(self, recipe):
        yaml_path = RECIPES_DIR / recipe / "prefect.yaml"
        content = yaml_path.read_text()
        for i, line in enumerate(content.splitlines(), start=1):
            assert len(line) <= 80, (
                f"{yaml_path} line {i} exceeds 80 characters "
                f"({len(line)} chars): {line!r}"
            )

    @pytest.mark.parametrize(
        "recipe",
        [d.name for d in sorted(RECIPES_DIR.iterdir()) if d.is_dir()],
    )
    def test_recipe_no_trailing_whitespace(self, recipe):
        yaml_path = RECIPES_DIR / recipe / "prefect.yaml"
        content = yaml_path.read_text()
        for i, line in enumerate(content.splitlines(), start=1):
            assert line == line.rstrip(), (
                f"{yaml_path} line {i} has trailing whitespace: {line!r}"
            )

    def test_generated_yaml_has_document_start_marker(self):
        contents = configure_project_by_recipe(
            "local", directory="/tmp/test", name="test"
        )
        create_default_prefect_yaml(".", name="test-project", contents=contents)

        generated = Path("prefect.yaml").read_text()
        assert generated.startswith("---"), (
            "Generated prefect.yaml is missing the '---' document start marker"
        )
