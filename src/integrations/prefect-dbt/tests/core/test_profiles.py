import os
import warnings
from datetime import datetime
from pathlib import Path

import pytest
import yaml
from prefect_dbt.core.profiles import (
    aresolve_profiles_yml,
    convert_block_references_to_env_vars,
    get_profiles_dir,
    load_profiles_yml,
    resolve_profiles_yml,
)

from prefect._internal.compatibility.deprecated import PrefectDeprecationWarning
from prefect.blocks.core import Block
from prefect.blocks.system import JSON, DateTime, Secret, String
from prefect.blocks.webhook import Webhook
from prefect.client.orchestration import get_client


def should_reraise_warning(warning):
    """
    Determine if a deprecation warning should be reraised based on the date.

    Deprecation warnings that have passed the date threshold should be reraised to
    ensure the deprecated code paths are removed.
    """
    message = str(warning.message)
    try:
        # Extract the date from the new message format
        date_str = message.split("not be available in new releases after ")[1].strip(
            "."
        )
        # Parse the date
        deprecation_date = datetime.strptime(date_str, "%b %Y").date().replace(day=1)

        # Check if the current date is after the start of the month following the deprecation date
        current_date = datetime.now().date().replace(day=1)
        return current_date > deprecation_date
    except Exception:
        # Reraise in cases of failure
        return True


@pytest.fixture
def ignore_prefect_deprecation_warnings():
    """
    Ignore deprecation warnings from the agent module to avoid
    test failures.
    """
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("ignore", category=PrefectDeprecationWarning)
        yield
        for warning in w:
            if isinstance(warning.message, PrefectDeprecationWarning):
                if should_reraise_warning(warning):
                    warnings.warn(warning.message, warning.category, stacklevel=2)


SAMPLE_PROFILE = {
    "jaffle_shop": {
        "outputs": {
            "dev": {
                "type": "duckdb",
                "path": "jaffle_shop.duckdb",
                "schema": "main",
                "threads": 4,
            }
        }
    }
}

VARIABLES_PROFILE = {
    "jaffle_shop_with_variable_reference": {
        "outputs": {
            "dev": {
                "type": "duckdb",
                "path": "jaffle_shop.duckdb",
                "schema": "main",
                "threads": 4,
            }
        },
        "target": "{{ prefect.variables.target }}",
    }
}

BLOCKS_PROFILE = {
    "jaffle_shop_with_variable_reference": {
        "outputs": {
            "dev": {
                "type": "duckdb",
                "path": "jaffle_shop.duckdb",
                "schema": "main",
                "threads": 4,
                "password": "{{ prefect.blocks.secret.my-password }}",
            }
        },
        "target": "dev",
    }
}


@pytest.fixture
def temp_profiles_dir(tmp_path):
    profiles_dir = tmp_path / ".dbt"
    profiles_dir.mkdir()

    profiles_path = profiles_dir / "profiles.yml"
    with open(profiles_path, "w") as f:
        yaml.dump(SAMPLE_PROFILE, f)

    return str(profiles_dir)


@pytest.fixture
def temp_variables_profiles_dir(tmp_path):
    profiles_dir = tmp_path / ".dbt"
    profiles_dir.mkdir()

    profiles_path = profiles_dir / "profiles.yml"
    with open(profiles_path, "w") as f:
        yaml.dump(VARIABLES_PROFILE, f)

    return str(profiles_dir)


@pytest.fixture
def temp_blocks_profiles_dir(tmp_path):
    """Create a temporary profiles directory with a profile that references a block."""
    profiles_dir = tmp_path / ".dbt"
    profiles_dir.mkdir()

    profiles_path = profiles_dir / "profiles.yml"
    with open(profiles_path, "w") as f:
        yaml.dump(BLOCKS_PROFILE, f)

    return str(profiles_dir)


def test_get_profiles_dir_default():
    if "DBT_PROFILES_DIR" in os.environ:
        del os.environ["DBT_PROFILES_DIR"]

    expected = os.path.expanduser("~/.dbt")
    assert get_profiles_dir() == expected


def test_get_profiles_dir_from_env(monkeypatch):
    test_path = "/custom/path"
    monkeypatch.setenv("DBT_PROFILES_DIR", test_path)
    assert get_profiles_dir() == test_path


def test_load_profiles_yml_success(temp_profiles_dir):
    profiles = load_profiles_yml(temp_profiles_dir)
    assert profiles == SAMPLE_PROFILE


def test_load_profiles_yml_default_dir(monkeypatch, temp_profiles_dir):
    monkeypatch.setenv("DBT_PROFILES_DIR", temp_profiles_dir)
    profiles = load_profiles_yml(None)
    assert profiles == SAMPLE_PROFILE


def test_load_profiles_yml_file_not_found():
    nonexistent_dir = "/path/that/does/not/exist"
    with pytest.raises(
        ValueError,
        match=f"No profiles.yml found at {os.path.join(nonexistent_dir, 'profiles.yml')}",
    ):
        load_profiles_yml(nonexistent_dir)


def test_load_profiles_yml_invalid_yaml(temp_profiles_dir):
    profiles_path = Path(temp_profiles_dir) / "profiles.yml"
    with open(profiles_path, "w") as f:
        f.write("invalid: yaml: content:\nindentation error")

    with pytest.raises(yaml.YAMLError):
        load_profiles_yml(temp_profiles_dir)


async def test_aresolve_profiles_yml_success(
    temp_profiles_dir,
):
    """Test that aresolve_profiles_yml creates and cleans up temporary directory."""
    async with aresolve_profiles_yml(temp_profiles_dir) as temp_dir:
        temp_path = Path(temp_dir)
        profiles_path = temp_path / "profiles.yml"

        # Check temporary directory exists and contains profiles.yml
        assert temp_path.exists()
        assert profiles_path.exists()

        # Verify contents match expected profiles
        loaded_profiles = yaml.safe_load(profiles_path.read_text())
        assert loaded_profiles == SAMPLE_PROFILE

    # Verify cleanup happened
    assert not temp_path.exists()


def test_resolve_profiles_yml_success(temp_profiles_dir):
    """Test that resolve_profiles_yml creates and cleans up temporary directory."""
    with resolve_profiles_yml(temp_profiles_dir) as temp_dir:
        temp_path = Path(temp_dir)
        profiles_path = temp_path / "profiles.yml"

        # Check temporary directory exists and contains profiles.yml
        assert temp_path.exists()
        assert profiles_path.exists()

        # Verify contents match expected profiles
        loaded_profiles = yaml.safe_load(profiles_path.read_text())
        assert loaded_profiles == SAMPLE_PROFILE

    # Verify cleanup happened
    assert not temp_path.exists()


async def test_aresolve_profiles_yml_error_cleanup(temp_profiles_dir):
    """Test that temporary directory is cleaned up even if an error occurs."""
    temp_path = None

    with pytest.raises(ValueError):
        async with aresolve_profiles_yml(temp_profiles_dir) as temp_dir:
            temp_path = Path(temp_dir)
            assert temp_path.exists()
            raise ValueError("Test error")

    # Verify cleanup happened despite error
    assert temp_path is not None
    assert not temp_path.exists()


def test_resolve_profiles_yml_error_cleanup(temp_profiles_dir):
    """Test that temporary directory is cleaned up even if an error occurs."""
    temp_path = None

    with pytest.raises(ValueError):
        with resolve_profiles_yml(temp_profiles_dir) as temp_dir:
            temp_path = Path(temp_dir)
            assert temp_path.exists()
            raise ValueError("Test error")

    # Verify cleanup happened despite error
    assert temp_path is not None
    assert not temp_path.exists()


async def test_aresolve_profiles_yml_resolves_variables(temp_variables_profiles_dir):
    """Test that variables in profiles.yml are properly resolved."""
    # Create a variable
    async with get_client() as client:
        await client._client.post(
            "/variables/", json={"name": "target", "value": "dev"}
        )

    # Use the context manager and verify variable resolution
    async with aresolve_profiles_yml(temp_variables_profiles_dir) as temp_dir:
        temp_path = Path(temp_dir)
        profiles_path = temp_path / "profiles.yml"

        # Verify contents have resolved variables
        loaded_profiles = yaml.safe_load(profiles_path.read_text())
        assert loaded_profiles["jaffle_shop_with_variable_reference"]["target"] == "dev"


def test_resolve_profiles_yml_resolves_variables(temp_variables_profiles_dir):
    with resolve_profiles_yml(temp_variables_profiles_dir) as temp_dir:
        temp_path = Path(temp_dir)
        profiles_path = temp_path / "profiles.yml"

        loaded_profiles = yaml.safe_load(profiles_path.read_text())
        assert loaded_profiles["jaffle_shop_with_variable_reference"]["target"] == "dev"


async def test_aresolve_profiles_yml_resolves_blocks(temp_blocks_profiles_dir):
    from prefect.blocks.system import Secret

    secret_block = Secret(value="super-secret-password")
    await secret_block.save("my-password", overwrite=True)

    async with aresolve_profiles_yml(temp_blocks_profiles_dir) as temp_dir:
        temp_path = Path(temp_dir)
        profiles_path = temp_path / "profiles.yml"

        loaded_profiles = yaml.safe_load(profiles_path.read_text())
        assert (
            loaded_profiles["jaffle_shop_with_variable_reference"]["outputs"]["dev"][
                "password"
            ]
            == "{{ env_var('PREFECT_BLOCKS_SECRET_MY_PASSWORD') }}"
        )


def test_resolve_profiles_yml_resolves_blocks(temp_blocks_profiles_dir):
    from prefect.blocks.system import Secret

    secret_block = Secret(value="super-secret-password")
    secret_block.save("my-password", overwrite=True)

    with resolve_profiles_yml(temp_blocks_profiles_dir) as temp_dir:
        temp_path = Path(temp_dir)
        profiles_path = temp_path / "profiles.yml"

        loaded_profiles = yaml.safe_load(profiles_path.read_text())
        assert (
            loaded_profiles["jaffle_shop_with_variable_reference"]["outputs"]["dev"][
                "password"
            ]
            == "{{ env_var('PREFECT_BLOCKS_SECRET_MY_PASSWORD') }}"
        )


class TestResolveBlockDocumentReferences:
    @pytest.fixture(autouse=True)
    def ignore_deprecation_warnings(self, ignore_prefect_deprecation_warnings):
        """Remove references to deprecated blocks when deprecation period is over."""
        pass

    @pytest.fixture()
    async def block_document_id(self):
        class ArbitraryBlock(Block):
            a: int
            b: str

        return await ArbitraryBlock(a=1, b="hello").save(
            name="arbitrary-block", overwrite=True
        )

    async def test_convert_block_references_to_env_vars_with_no_block_document_references(
        self,
    ):
        assert await convert_block_references_to_env_vars({"key": "value"}) == {
            "key": "value"
        }

    async def test_convert_block_references_to_env_vars_with_one_block_document_reference(
        self, block_document_id
    ):
        async with get_client() as prefect_client:
            assert {
                "key": {"a": 1, "b": "hello"}
            } == await convert_block_references_to_env_vars(
                {"key": {"$ref": {"block_document_id": block_document_id}}},
                client=prefect_client,
            )

    async def test_convert_block_references_to_env_vars_with_nested_block_document_references(
        self, block_document_id
    ):
        async with get_client() as prefect_client:
            template = {
                "key": {
                    "nested_key": {"$ref": {"block_document_id": block_document_id}},
                    "other_nested_key": {
                        "$ref": {"block_document_id": block_document_id}
                    },
                }
            }
            block_document = await prefect_client.read_block_document(block_document_id)

            result = await convert_block_references_to_env_vars(
                template, client=prefect_client
            )

            assert result == {
                "key": {
                    "nested_key": block_document.data,
                    "other_nested_key": block_document.data,
                }
            }

    async def test_convert_block_references_to_env_vars_with_list_of_block_document_references(
        self, block_document_id
    ):
        async with get_client() as prefect_client:
            template = [{"$ref": {"block_document_id": block_document_id}}]
            block_document = await prefect_client.read_block_document(block_document_id)

            result = await convert_block_references_to_env_vars(
                template, client=prefect_client
            )

        assert result == [block_document.data]

    async def test_convert_block_references_to_env_vars_with_dot_delimited_syntax(
        self, block_document_id
    ):
        async with get_client() as prefect_client:
            template = {"key": "{{ prefect.blocks.arbitraryblock.arbitrary-block }}"}

            result = await convert_block_references_to_env_vars(
                template, client=prefect_client
            )

        assert result == {
            "key": "{{ env_var('PREFECT_BLOCKS_ARBITRARYBLOCK_ARBITRARY_BLOCK') }}"
        }

    async def test_convert_block_references_to_env_vars_raises_on_multiple_placeholders(
        self, block_document_id
    ):
        async with get_client() as prefect_client:
            template = {
                "key": (
                    "{{ prefect.blocks.arbitraryblock.arbitrary-block }} {{"
                    " another_placeholder }}"
                )
            }

            with pytest.raises(
                ValueError,
                match=(
                    "Only a single block placeholder is allowed in a string and no"
                    " surrounding text is allowed."
                ),
            ):
                await convert_block_references_to_env_vars(
                    template, client=prefect_client
                )

    async def test_convert_block_references_to_env_vars_raises_on_extra_text(
        self, block_document_id
    ):
        async with get_client() as prefect_client:
            template = {
                "key": "{{ prefect.blocks.arbitraryblock.arbitrary-block }} extra text"
            }

            with pytest.raises(
                ValueError,
                match=(
                    "Only a single block placeholder is allowed in a string and no"
                    " surrounding text is allowed."
                ),
            ):
                await convert_block_references_to_env_vars(
                    template, client=prefect_client
                )

    async def test_convert_block_references_to_env_vars_does_not_change_standard_placeholders(
        self,
    ):
        template = {"key": "{{ standard_placeholder }}"}

        result = await convert_block_references_to_env_vars(template)

        assert result == template

    async def test_resolve_block_document_unpacks_system_blocks(self):
        await JSON(value={"key": "value"}).save(name="json-block")
        await Secret(value="N1nj4C0d3rP@ssw0rd!").save(name="secret-block")
        await DateTime(value="2020-01-01T00:00:00Z").save(name="datetime-block")
        await String(value="hello").save(name="string-block")

        template = {
            "json": "{{ prefect.blocks.json.json-block }}",
            "secret": "{{ prefect.blocks.secret.secret-block }}",
            "datetime": "{{ prefect.blocks.date-time.datetime-block }}",
            "string": "{{ prefect.blocks.string.string-block }}",
        }

        result = await convert_block_references_to_env_vars(template)
        assert result == {
            "datetime": "{{ env_var('PREFECT_BLOCKS_DATE_TIME_DATETIME_BLOCK') }}",
            "json": "{{ env_var('PREFECT_BLOCKS_JSON_JSON_BLOCK') }}",
            "secret": "{{ env_var('PREFECT_BLOCKS_SECRET_SECRET_BLOCK') }}",
            "string": "{{ env_var('PREFECT_BLOCKS_STRING_STRING_BLOCK') }}",
        }

    async def test_resolve_block_document_system_block_resolves_dict_keypath(self):
        # for backwards compatibility system blocks can be referenced directly
        # they should still be able to access nested keys
        await JSON(value={"key": {"nested-key": "nested_value"}}).save(
            name="nested-json-block"
        )
        template = {
            "value": "{{ prefect.blocks.json.nested-json-block}}",
            "keypath": "{{ prefect.blocks.json.nested-json-block.key }}",
            "nested_keypath": "{{ prefect.blocks.json.nested-json-block.key.nested-key }}",
        }

        result = await convert_block_references_to_env_vars(template)
        assert result == {
            "keypath": "{{ env_var('PREFECT_BLOCKS_JSON_NESTED_JSON_BLOCK_KEY') }}",
            "nested_keypath": "{{ env_var('PREFECT_BLOCKS_JSON_NESTED_JSON_BLOCK_KEY_NESTED_KEY') }}",
            "value": "{{ env_var('PREFECT_BLOCKS_JSON_NESTED_JSON_BLOCK') }}",
        }

    async def test_resolve_block_document_resolves_dict_keypath(self):
        await JSON(value={"key": {"nested-key": "nested_value"}}).save(
            name="nested-json-block-2"
        )
        template = {
            "value": "{{ prefect.blocks.json.nested-json-block-2.value }}",
            "keypath": "{{ prefect.blocks.json.nested-json-block-2.value.key }}",
            "nested_keypath": (
                "{{ prefect.blocks.json.nested-json-block-2.value.key.nested-key }}"
            ),
        }

        result = await convert_block_references_to_env_vars(template)
        assert result == {
            "keypath": "{{ env_var('PREFECT_BLOCKS_JSON_NESTED_JSON_BLOCK_2_VALUE_KEY') }}",
            "nested_keypath": "{{ env_var('PREFECT_BLOCKS_JSON_NESTED_JSON_BLOCK_2_VALUE_KEY_NESTED_KEY') }}",
            "value": "{{ env_var('PREFECT_BLOCKS_JSON_NESTED_JSON_BLOCK_2_VALUE') }}",
        }

    async def test_resolve_block_document_resolves_list_keypath(self):
        await JSON(value={"key": ["value1", "value2"]}).save(name="json-list-block")
        await JSON(value=["value1", "value2"]).save(name="list-block")
        await JSON(
            value={"key": ["value1", {"nested": ["value2", "value3"]}, "value4"]}
        ).save(name="nested-json-list-block")
        template = {
            "json_list": "{{ prefect.blocks.json.json-list-block.value.key[0] }}",
            "list": "{{ prefect.blocks.json.list-block.value[1] }}",
            "nested_json_list": (
                "{{ prefect.blocks.json.nested-json-list-block.value.key[1].nested[1] }}"
            ),
        }

        result = await convert_block_references_to_env_vars(template)
        assert result == {
            "json_list": "{{ env_var('PREFECT_BLOCKS_JSON_JSON_LIST_BLOCK_VALUE_KEY_0') }}",
            "list": "{{ env_var('PREFECT_BLOCKS_JSON_LIST_BLOCK_VALUE_1') }}",
            "nested_json_list": "{{ env_var('PREFECT_BLOCKS_JSON_NESTED_JSON_LIST_BLOCK_VALUE_KEY_1_NESTED_1') }}",
        }

    async def test_resolve_block_document_raises_on_invalid_keypath(self):
        await JSON(value={"key": {"nested_key": "value"}}).save(
            name="nested-json-block-3"
        )
        json_template = {
            "json": "{{ prefect.blocks.json.nested-json-block-3.value.key.does_not_exist }}",
        }
        with pytest.raises(ValueError, match="Could not resolve the keypath"):
            await convert_block_references_to_env_vars(json_template)

        await JSON(value=["value1", "value2"]).save(name="index-error-block")
        index_error_template = {
            "index_error": "{{ prefect.blocks.json.index-error-block.value[3] }}",
        }
        with pytest.raises(ValueError, match="Could not resolve the keypath"):
            await convert_block_references_to_env_vars(index_error_template)

        await Webhook(url="https://example.com").save(name="webhook-block")
        webhook_template = {
            "webhook": "{{ prefect.blocks.webhook.webhook-block.value }}",
        }
        with pytest.raises(ValueError, match="Could not resolve the keypath"):
            await convert_block_references_to_env_vars(webhook_template)

    async def test_resolve_block_document_resolves_block_attribute(self):
        await Webhook(url="https://example.com").save(name="webhook-block-2")

        template = {
            "block_attribute": "{{ prefect.blocks.webhook.webhook-block-2.url }}",
        }
        result = await convert_block_references_to_env_vars(template)

        assert result == {
            "block_attribute": "{{ env_var('PREFECT_BLOCKS_WEBHOOK_WEBHOOK_BLOCK_2_URL') }}",
        }
