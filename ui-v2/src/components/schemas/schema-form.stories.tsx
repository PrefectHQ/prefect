import type { Meta, StoryFn } from "@storybook/react";
import { useState } from "react";
import { SchemaForm } from "./schema-form";
import { PrefectKind } from "./types/prefect-kind";
import { PrefectSchemaObject } from "./types/schemas";

const schema: PrefectSchemaObject = {
	type: "object",
	properties: {
		none: {
			type: "null",
			title: "None",
		},
		string: {
			type: "string",
			title: "String",
			description: "This is a description",
		},
		string_required: {
			type: "string",
			title: "String Required",
		},
		string_enum: {
			type: "string",
			title: "String Enum",
			enum: ["foo", "bar", "baz"],
			description: "This is a description",
		},
		string_format_date: {
			type: "string",
			title: "String Format Date",
			format: "date",
		},
		string_format_datetime: {
			type: "string",
			title: "String Format DateTime",
			format: "date-time",
		},
		string_format_json: {
			type: "string",
			title: "String Format JSON",
			format: "json-string",
		},
		integer: {
			type: "integer",
			title: "Integer",
		},
		integer_enum: {
			type: "integer",
			title: "Integer Enum",
			enum: [1, 2, 3],
		},
		number: {
			type: "number",
			title: "Number",
		},
		number_enum: {
			type: "number",
			title: "Number Enum",
			enum: [1.5, 2.5, 3.5, 4],
		},
		boolean: {
			type: "boolean",
			title: "Boolean",
		},
		boolean_enum: {
			type: "boolean",
			title: "Boolean Enum",
			enum: [true, false],
		},
		array_string_enum: {
			type: "array",
			title: "Array of strings",
			items: {
				type: "string",
				enum: ["tag1", "tag2", "tag3"],
			},
		},
		array_integer_enum: {
			type: "array",
			title: "Array of integers",
			items: {
				type: "integer",
				enum: [1, 2, 3],
			},
		},
		array_number_enum: {
			type: "array",
			title: "Array of numbers",
			items: {
				type: "number",
				enum: [1.5, 2.5, 3.5],
			},
		},
		array_boolean_enum: {
			type: "array",
			title: "Array of booleans",
			items: {
				type: "boolean",
				enum: [true, false],
			},
		},
		array_reference_enum: {
			type: "array",
			title: "Array of references",
			items: {
				$ref: "#/definitions/type",
			},
		},
		object: {
			type: "object",
			title: "Object",
			properties: {
				foo: {
					type: "string",
					title: "Foo",
				},
			},
			required: ["foo"],
		},
		reference: {
			title: "User Reference",
			$ref: "#/definitions/user",
		},
		preject_kind_json: {
			type: "object",
			title: "Prefect Kind JSON",
		},
		preject_kind_none: {
			type: "string",
			title: "Prefect Kind None",
		},
		//@ts-expect-error pydantic can create properties without a type
		unknown: {
			title: "Unknown",
		},
		//@ts-expect-error pydantic can create properties without a type
		unknown_enum: {
			title: "Unknown Enum",
			enum: ["foo", "bar", "baz"],
		},
		any_of: {
			type: "object",
			title: "Any Of",
			anyOf: [
				{
					type: "string",
					title: "String",
				},
				{
					type: "number",
					title: "Number",
				},
				{
					type: "boolean",
					title: "Boolean",
				},
				{
					type: "object",
					title: "Object",
					required: ["foo"],
					properties: {
						foo: { type: "string", title: "Foo" },
						bar: { type: "number", title: "Bar" },
						baz: { type: "boolean", title: "Baz" },
					},
				},
				{
					$ref: "#/definitions/user",
				},
			],
		},
		all_of: {
			type: "object",
			title: "All Of",
			allOf: [
				{
					type: "object",
					title: "Object",
					properties: {
						foo: { type: "string", title: "Foo" },
					},
				},
				{
					$ref: "#/definitions/user",
				},
			],
		},
	},
	definitions: {
		user: {
			type: "object",
			title: "User",
			properties: {
				name: {
					type: "string",
					title: "Name",
				},
			},
		},
		type: {
			type: "string",
			title: "Type",
			enum: ["Type1", "Type2", "Type3"],
		},
	},
	required: ["string_required"],
};

const kinds: PrefectKind[] = ["none", "json", "jinja", "workspace_variable"];

const meta = {
	title: "Components/SchemaForm",
	component: SchemaForm,
	parameters: {
		layout: "centered",
	},
} satisfies Meta<typeof SchemaForm>;

export default meta;

export const Default: StoryFn<typeof SchemaForm> = () => {
	const [values, setValues] = useState<Record<string, unknown>>({
		name: "John Doe",
		age: 30,
		preject_kind_json: {
			__prefect_kind: "json",
			value: JSON.stringify({
				foo: "bar",
			}),
		},
		preject_kind_none: {
			__prefect_kind: "none",
			value: "hello",
		},
		any_of: { name: "Prefect" },
	});

	const errors = {};

	return (
		<div className="flex gap-4 p-16">
			<SchemaForm
				values={values}
				schema={schema}
				kinds={kinds}
				errors={errors}
				onValuesChange={setValues}
			/>

			<pre>{JSON.stringify(values, null, 2)}</pre>
		</div>
	);
};
