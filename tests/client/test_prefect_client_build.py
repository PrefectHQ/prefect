from pathlib import Path

import pytest
import toml


def get_dependencies_from_pyproject(pyproject_path: Path) -> dict[str, str]:
    pyproject_data = toml.load(pyproject_path)

    dependencies = pyproject_data.get("project", {}).get("dependencies", [])
    return {dep.split(">=")[0].strip(): dep for dep in dependencies}


def pytest_generate_tests(metafunc: pytest.Metafunc):
    if "client_dependency" in metafunc.fixturenames:
        root_dir = Path(__file__).parent.parent.parent
        client_pyproject = root_dir / "client" / "pyproject.toml"
        client_deps = get_dependencies_from_pyproject(client_pyproject)

        # Generate test cases for each dependency
        test_cases = [
            (dep_name, dep_spec) for dep_name, dep_spec in client_deps.items()
        ]
        metafunc.parametrize("client_dependency", test_cases)


@pytest.fixture(scope="module")
def prefect_dependencies() -> dict[str, str]:
    root_dir = Path(__file__).parent.parent.parent
    prefect_pyproject = root_dir / "pyproject.toml"
    return get_dependencies_from_pyproject(prefect_pyproject)


def test_client_dependency_matches_prefect(
    client_dependency: tuple[str, str], prefect_dependencies: dict[str, str]
):
    """The `prefect-client` package dependencies must have constraints that match those
    of the main `prefect` package."""
    dep_name, client_spec = client_dependency

    assert dep_name in prefect_dependencies, (
        f"Dependency '{dep_name}' exists in client but not in prefect"
    )
    prefect_spec = prefect_dependencies[dep_name]
    assert client_spec == prefect_spec, (
        f"Dependency '{dep_name}' has different specifiers:\n"
        f"  prefect: {prefect_spec}\n"
        f"  client:  {client_spec}"
    )
