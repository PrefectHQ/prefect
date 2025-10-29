import uuid
from typing import Any, Dict

import pytest

from prefect.blocks.core import Block
from prefect.blocks.webhook import Webhook
from prefect.client.orchestration import PrefectClient
from prefect.utilities.annotations import NotSet
from prefect.utilities.templating import (
    PlaceholderType,
    apply_values,
    find_placeholders,
    resolve_block_document_references,
    resolve_variables,
)


class TestFindPlaceholders:
    def test_empty_template(self):
        template = ""
        placeholders = find_placeholders(template)
        assert len(placeholders) == 0

    def test_single_placeholder(self):
        template = "Hello {{name}}!"
        placeholders = find_placeholders(template)
        assert len(placeholders) == 1
        assert placeholders.pop().name == "name"

    def test_multiple_placeholders(self):
        template = "Hello {{first_name}} {{last_name}}!"
        placeholders = find_placeholders(template)
        assert len(placeholders) == 2
        names = set(p.name for p in placeholders)
        assert names == {"first_name", "last_name"}

    def test_nested_placeholders(self):
        template = {"greeting": "Hello {{name}}!", "message": "{{greeting}}"}
        placeholders = find_placeholders(template)
        assert len(placeholders) == 2
        names = set(p.name for p in placeholders)
        assert names == {"name", "greeting"}

    def test_mixed_template(self):
        template = "Hello {{name}}! Your balance is ${{balance}}."
        placeholders = find_placeholders(template)
        assert len(placeholders) == 2
        names = set(p.name for p in placeholders)
        assert names == {"name", "balance"}

    def test_invalid_template(self):
        template = ("{{name}}!",)
        with pytest.raises(ValueError):
            find_placeholders(template)

    def test_nested_templates(self):
        template = {"greeting": "Hello {{name}}!", "message": {"text": "{{greeting}}"}}
        placeholders = find_placeholders(template)
        assert len(placeholders) == 2
        names = set(p.name for p in placeholders)
        assert names == {"name", "greeting"}

    def test_template_with_duplicates(self):
        template = "{{x}}{{x}}"
        placeholders = find_placeholders(template)
        assert len(placeholders) == 1
        assert placeholders.pop().name == "x"

    def test_template_with_unconventional_spacing(self):
        template = "Hello {{    first_name }} {{ last_name }}!"
        placeholders = find_placeholders(template)
        assert len(placeholders) == 2
        names = set(p.name for p in placeholders)
        assert names == {"first_name", "last_name"}

    def test_finds_block_document_placeholders(self):
        template = "Hello {{prefect.blocks.document.name}}!"
        placeholders = find_placeholders(template)
        assert len(placeholders) == 1
        placeholder = placeholders.pop()
        assert placeholder.name == "prefect.blocks.document.name"
        assert placeholder.type is PlaceholderType.BLOCK_DOCUMENT

    def test_finds_env_var_placeholders(self, monkeypatch):
        monkeypatch.setenv("MY_ENV_VAR", "VALUE")
        template = "Hello {{$MY_ENV_VAR}}!"
        placeholders = find_placeholders(template)
        assert len(placeholders) == 1
        placeholder = placeholders.pop()
        assert placeholder.name == "$MY_ENV_VAR"
        assert placeholder.type is PlaceholderType.ENV_VAR

    def test_apply_values_clears_placeholder_for_missing_env_vars(self):
        template = "{{ $MISSING_ENV_VAR }}"
        values = {"ANOTHER_ENV_VAR": "test_value"}
        result = apply_values(template, values)
        assert result == ""

    def test_finds_nested_env_var_placeholders(self, monkeypatch):
        monkeypatch.setenv("GREETING", "VALUE")
        template = {"greeting": "Hello {{name}}!", "message": {"text": "{{$GREETING}}"}}
        placeholders = find_placeholders(template)
        assert len(placeholders) == 2
        names = set(p.name for p in placeholders)
        assert names == {"name", "$GREETING"}

        types = set(p.type for p in placeholders)
        assert types == {PlaceholderType.STANDARD, PlaceholderType.ENV_VAR}

    @pytest.mark.parametrize(
        "template,expected",
        [
            (
                '{"greeting": "Hello {{name}}!", "message": {"text": "{{$$}}"}}',
                '{"greeting": "Hello Dan!", "message": {"text": ""}}',
            ),
            (
                '{"greeting": "Hello {{name}}!", "message": {"text": "{{$GREETING}}"}}',
                '{"greeting": "Hello Dan!", "message": {"text": ""}}',
            ),
        ],
    )
    def test_invalid_env_var_placeholder(self, template, expected):
        values = {"name": "Dan"}
        result = apply_values(template, values)
        assert result == expected


class TestApplyValues:
    def test_apply_values_simple_string_with_one_placeholder(self):
        assert apply_values("Hello, {{name}}!", {"name": "Alice"}) == "Hello, Alice!"

    def test_apply_values_simple_string_with_multiple_placeholders(self):
        assert (
            apply_values(
                "Hello, {{first_name}} {{last_name}}!",
                {"first_name": "Alice", "last_name": "Smith"},
            )
            == "Hello, Alice Smith!"
        )

    def test_apply_values_dictionary_with_placeholders(self):
        template = {"name": "{{first_name}} {{last_name}}", "age": "{{age}}"}
        values = {"first_name": "Alice", "last_name": "Smith", "age": 30}
        assert apply_values(template, values) == {"name": "Alice Smith", "age": 30}

    def test_apply_values_dictionary_with_unset_value(self):
        template = {"last_name": "{{last_name}}", "age": "{{age}}"}
        values = {"first_name": "Alice", "age": 30}
        assert apply_values(template, values) == {"age": 30}

    def test_apply_values_dictionary_with_null(self):
        template = {"last_name": None, "age": "{{age}}"}
        values = {"first_name": "Alice", "age": 30}
        assert apply_values(template, values) == {"last_name": None, "age": 30}

    def test_apply_values_nested_dictionary_with_placeholders(self):
        template = {
            "name": {"first_name": "{{ first_name }}", "last_name": "{{ last_name }}"},
            "age": "{{age}}",
        }
        values = {"first_name": "Alice", "last_name": "Smith", "age": 30}
        assert apply_values(template, values) == {
            "name": {"first_name": "Alice", "last_name": "Smith"},
            "age": 30,
        }

    def test_apply_values_dictionary_with_notset_value_removed(self):
        template = {"name": NotSet, "age": "{{age}}"}
        values = {"age": 30}
        assert apply_values(template, values) == {"age": 30}

    def test_apply_values_dictionary_with_NotSet_value_not_removed(self):
        template = {"name": NotSet, "age": "{{age}}"}
        values = {"age": 30}
        assert apply_values(template, values, remove_notset=False) == {
            "name": NotSet,
            "age": 30,
        }

    def test_apply_values_string_with_missing_value_not_removed(self):
        template = {"name": "Bob {{last_name}}", "age": "{{age}}"}
        values = {"age": 30}
        assert apply_values(template, values, remove_notset=False) == {
            "name": "Bob {{last_name}}",
            "age": 30,
        }

    def test_apply_values_nested_with_NotSet_value_not_removed(self):
        template = [{"top_key": {"name": NotSet, "age": "{{age}}"}}]
        values = {"age": 30}
        assert apply_values(template, values, remove_notset=False) == [
            {
                "top_key": {
                    "name": NotSet,
                    "age": 30,
                }
            }
        ]

    def test_apply_values_list_with_placeholders(self):
        template = [
            "Hello, {{first_name}} {{last_name}}!",
            {"name": "{{first_name}} {{last_name}}"},
        ]
        values = {"first_name": "Alice", "last_name": "Smith"}
        assert apply_values(template, values) == [
            "Hello, Alice Smith!",
            {"name": "Alice Smith"},
        ]

    def test_apply_values_integer_input(self):
        assert apply_values(123, {"name": "Alice"}) == 123

    def test_apply_values_float_input(self):
        assert apply_values(3.14, {"pi": 3.14}) == 3.14

    def test_apply_values_boolean_input(self):
        assert apply_values(True, {"flag": False}) is True

    def test_apply_values_none_input(self):
        assert apply_values(None, {"key": "value"}) is None

    def test_does_not_apply_values_to_block_document_placeholders(self):
        template = "Hello {{prefect.blocks.document.name}}!"
        assert apply_values(template, {"name": "Alice"}) == template

    def test_apply_values_with_dot_delimited_placeholder_str(self):
        template = "Hello {{ person.name }}!"
        assert apply_values(template, {"person": {"name": "Arthur"}}) == "Hello Arthur!"

    def test_apply_values_with_dot_delimited_placeholder_str_with_list(self):
        template = "Hello {{ people[0].name }}!"
        assert (
            apply_values(template, {"people": [{"name": "Arthur"}]}) == "Hello Arthur!"
        )

    def test_apply_values_with_dot_delimited_placeholder_dict(self):
        template = {"right now we need": "{{ people.superman }}"}
        values = {"people": {"superman": {"first_name": "Superman", "age": 30}}}
        assert apply_values(template, values) == {
            "right now we need": {"first_name": "Superman", "age": 30}
        }

    def test_apply_values_with_dot_delimited_placeholder_with_list(self):
        template = {"right now we need": "{{ people[0] }}"}
        values = {"people": [{"first_name": "Superman", "age": 30}]}
        assert apply_values(template, values) == {
            "right now we need": {"first_name": "Superman", "age": 30}
        }

    def test_apply_values_warns_on_notset_value(self, caplog: pytest.LogCaptureFixture):
        template = "{{name}}"
        apply_values(template, values={}, warn_on_notset=True)
        assert (
            "Value for placeholder 'name' not found in provided values." in caplog.text
        )

    def test_apply_values_warns_on_notset_value_dict(
        self, caplog: pytest.LogCaptureFixture
    ):
        template = {"name": "{{name}}"}
        apply_values(template, values={}, warn_on_notset=True)
        assert (
            "Value for placeholder 'name' not found in provided values." in caplog.text
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

    async def test_resolve_block_document_references_with_no_block_document_references(
        self,
    ):
        assert await resolve_block_document_references({"key": "value"}) == {
            "key": "value"
        }

    async def test_resolve_block_document_references_with_one_block_document_reference(
        self, prefect_client, block_document_id
    ):
        assert {
            "key": {"a": 1, "b": "hello"}
        } == await resolve_block_document_references(
            {"key": {"$ref": {"block_document_id": block_document_id}}},
            client=prefect_client,
        )

    async def test_resolve_block_document_references_with_nested_block_document_references(
        self, prefect_client, block_document_id
    ):
        template = {
            "key": {
                "nested_key": {"$ref": {"block_document_id": block_document_id}},
                "other_nested_key": {"$ref": {"block_document_id": block_document_id}},
            }
        }
        block_document = await prefect_client.read_block_document(block_document_id)

        result = await resolve_block_document_references(
            template, client=prefect_client
        )

        assert result == {
            "key": {
                "nested_key": block_document.data,
                "other_nested_key": block_document.data,
            }
        }

    async def test_resolve_block_document_references_with_list_of_block_document_references(
        self, prefect_client, block_document_id
    ):
        template = [{"$ref": {"block_document_id": block_document_id}}]
        block_document = await prefect_client.read_block_document(block_document_id)

        result = await resolve_block_document_references(
            template, client=prefect_client
        )

        assert result == [block_document.data]

    async def test_resolve_block_document_references_with_dot_delimited_syntax(
        self, prefect_client, block_document_id
    ):
        template = {"key": "{{ prefect.blocks.arbitraryblock.arbitrary-block }}"}

        block_document = await prefect_client.read_block_document(block_document_id)

        result = await resolve_block_document_references(
            template, client=prefect_client
        )

        assert result == {"key": block_document.data}

    async def test_resolve_block_document_references_raises_on_multiple_placeholders(
        self, prefect_client
    ):
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
            await resolve_block_document_references(template, client=prefect_client)

    async def test_resolve_block_document_references_raises_on_extra_text(
        self, prefect_client
    ):
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
            await resolve_block_document_references(template, client=prefect_client)

    async def test_resolve_block_document_references_does_not_change_standard_placeholders(
        self,
    ):
        template = {"key": "{{ standard_placeholder }}"}

        result = await resolve_block_document_references(template)

        assert result == template

    async def test_resolve_block_document_resolves_block_attribute(self):
        await Webhook(url="https://example.com").save(name="webhook-block-2")

        template = {
            "block_attribute": "{{ prefect.blocks.webhook.webhook-block-2.url }}",
        }
        result = await resolve_block_document_references(template)

        assert result == {
            "block_attribute": "https://example.com",
        }


class TestResolveVariables:
    @pytest.fixture
    async def variable_1(self, prefect_client: PrefectClient):
        res = await prefect_client._client.post(
            "/variables/",
            json={"name": f"test_variable_{uuid.uuid4().hex}", "value": "test_value_1"},
        )
        return res.json()

    @pytest.fixture
    async def variable_2(self, prefect_client: PrefectClient):
        res = await prefect_client._client.post(
            "/variables/",
            json={"name": f"test_variable_{uuid.uuid4().hex}", "value": "test_value_2"},
        )
        return res.json()

    async def test_resolve_string_no_placeholders(self, prefect_client: PrefectClient):
        template = "This is a simple string."
        result = await resolve_variables(template, client=prefect_client)
        assert result == template

    async def test_resolve_string_with_standard_placeholder(
        self, variable_1, prefect_client: PrefectClient
    ):
        template = (
            "This is a string with a placeholder: {{"
            f" prefect.variables.{variable_1['name']} }}}}."
        )
        expected = "This is a string with a placeholder: test_value_1."
        result = await resolve_variables(template, client=prefect_client)
        assert result == expected

    async def test_resolve_string_with_multiple_standard_placeholders(
        self, variable_1, variable_2, prefect_client: PrefectClient
    ):
        template = (
            f"{{{{ prefect.variables.{variable_1['name']} }}}} - {{{{"
            f" prefect.variables.{variable_2['name']} }}}}"
        )
        expected = "test_value_1 - test_value_2"
        result = await resolve_variables(template, client=prefect_client)
        assert result == expected

    async def test_resolve_dict(self, variable_1, prefect_client: PrefectClient):
        template: Dict[str, Any] = {
            "key1": "value1",
            "key2": f"{{{{ prefect.variables.{variable_1['name']} }}}}",
        }
        expected = {"key1": "value1", "key2": "test_value_1"}
        result = await resolve_variables(template, client=prefect_client)
        assert result == expected

    async def test_resolve_nested_dict(
        self, variable_1, variable_2, prefect_client: PrefectClient
    ):
        template: Dict[str, Any] = {
            "key1": "value1",
            "key2": f"{{{{ prefect.variables.{variable_1['name']} }}}}",
            "key3": {"key4": f"{{{{ prefect.variables.{variable_2['name']} }}}}"},
        }
        expected = {
            "key1": "value1",
            "key2": "test_value_1",
            "key3": {"key4": "test_value_2"},
        }
        result = await resolve_variables(template, client=prefect_client)
        assert result == expected

    async def test_resolve_list(self, variable_1, prefect_client: PrefectClient):
        template = ["value1", f"{{{{ prefect.variables.{variable_1['name']} }}}}", 42]
        expected = ["value1", "test_value_1", 42]
        result = await resolve_variables(template, client=prefect_client)
        assert result == expected

    async def test_resolve_non_string_types(self, prefect_client: PrefectClient):
        template = 42
        result = await resolve_variables(template, client=prefect_client)
        assert result == template

    async def test_resolve_does_not_template_other_placeholder_types(
        self, prefect_client: PrefectClient
    ):
        template = {
            "key": "{{ another_placeholder }}",
            "key2": "{{ prefect.blocks.arbitraryblock.arbitrary-block }}",
            "key3": "{{ $another_placeholder }}",
        }
        result = await resolve_variables(template, client=prefect_client)
        assert result == template

    async def test_resolve_clears_placeholder_for_missing_variable(
        self, prefect_client: PrefectClient
    ):
        template = "{{ prefect.variables.missing_variable }}"
        result = await resolve_variables(template, client=prefect_client)
        assert result == ""

    async def test_resolve_clears_placeholders_for_missing_variables(
        self, prefect_client: PrefectClient
    ):
        template = (
            "{{ prefect.variables.missing_variable_1 }} - {{"
            " prefect.variables.missing_variable_2 }}"
        )
        result = await resolve_variables(template, client=prefect_client)
        assert result == " - "
