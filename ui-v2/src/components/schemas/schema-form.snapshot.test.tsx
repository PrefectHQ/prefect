import { render } from "@testing-library/react";
import type { SchemaObject } from "openapi-typescript";
import { describe, expect, test } from "vitest";
import { SchemaForm, type SchemaFormProps } from "./schema-form";

/**
 * 🔍 Snapshot Tests
 *
 * ⚠️ These snapshot tests are order dependent because of `useId` which produces
 * a random id that is order dependent on how many times useId is called.
 * We could mock react's useId to return a deterministic id. However radix-ui
 * had their own wrapper around useId that we would also need to mock. Which
 * we've been unable to do so far.
 *
 * https://github.com/radix-ui/primitives/discussions/3393
 *
 * 🔄 Running tests in a different order will cause snapshots to fail. Such as
 * when adding a new test to the middle of the list.
 */

function TestSchemaForm({
	schema = { type: "object", properties: {} },
	kinds = [],
	errors = [],
	values = {},
	onValuesChange = () => {},
}: Partial<SchemaFormProps>) {
	return (
		<SchemaForm
			schema={schema}
			kinds={kinds}
			errors={errors}
			values={values}
			onValuesChange={onValuesChange}
		/>
	);
}

describe("property.type", () => {
	describe("string", () => {
		test("", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("with value", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string" },
				},
			};
			const { container } = render(
				<TestSchemaForm schema={schema} values={{ name: "foo" }} />,
			);

			expect(container).toMatchSnapshot();
		});

		test("with default", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", default: "foo" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("format:date", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", format: "date" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("format:date with value", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", format: "date" },
				},
			};
			const { container } = render(
				<TestSchemaForm schema={schema} values={{ name: "2024-01-01" }} />,
			);

			expect(container).toMatchSnapshot();
		});

		test("format:date with default", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", format: "date", default: "2024-01-01" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("format:date-time", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", format: "date-time" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("format:date-time with value", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", format: "date-time" },
				},
			};
			const { container } = render(
				<TestSchemaForm
					schema={schema}
					values={{ name: "2024-01-01T00:00:00Z" }}
				/>,
			);

			expect(container).toMatchSnapshot();
		});

		test("format:date-time with default", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: {
						type: "string",
						format: "date-time",
						default: "2024-01-01T00:00:00Z",
					},
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("format:json-string", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", format: "json-string" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("format:json-string with value", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", format: "json-string" },
				},
			};
			const { container } = render(
				<TestSchemaForm schema={schema} values={{ name: '{"foo": "bar"}' }} />,
			);

			expect(container).toMatchSnapshot();
		});

		test("format:json-string with default", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: {
						type: "string",
						format: "json-string",
						default: '{"foo": "bar"}',
					},
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("enum", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", enum: ["foo", "bar"] },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("enum with value", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", enum: ["foo", "bar"] },
				},
			};
			const { container } = render(
				<TestSchemaForm schema={schema} values={{ name: "foo" }} />,
			);

			expect(container).toMatchSnapshot();
		});

		test("enum with default", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", enum: ["foo", "bar"], default: "foo" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});
	});

	describe("number", () => {
		test("base", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "number" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("with value", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "number" },
				},
			};
			const { container } = render(
				<TestSchemaForm schema={schema} values={{ name: 123.45 }} />,
			);

			expect(container).toMatchSnapshot();
		});

		test("with default", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "number", default: 123.45 },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("enum", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "number", enum: [1, 2.5, 3.9] },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});
	});

	describe("integer", () => {
		test("base", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "number" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("with value", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "number" },
				},
			};
			const { container } = render(
				<TestSchemaForm schema={schema} values={{ name: 123 }} />,
			);

			expect(container).toMatchSnapshot();
		});

		test("with default", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "number", default: 123 },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("enum", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "number", enum: [1, 2, 3] },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});
	});

	describe("boolean", () => {
		test("base", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "boolean" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("with value", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "boolean" },
				},
			};
			const { container } = render(
				<TestSchemaForm schema={schema} values={{ name: true }} />,
			);

			expect(container).toMatchSnapshot();
		});

		test("with default", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "boolean", default: true },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("enum", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "boolean", enum: [true, false] },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});
	});

	describe("null", () => {
		test("base", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "null" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});
	});

	describe("unknown", () => {
		test("base", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: {
						// sometimes pydantic creates a property with an undefined type
						type: undefined as unknown as (
							| "string"
							| "number"
							| "boolean"
							| "object"
							| "null"
							| "integer"
							| "array"
						)[],
					},
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});

		test("with value", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: {
						// sometimes pydantic creates a property with an undefined type
						type: undefined as unknown as (
							| "string"
							| "number"
							| "boolean"
							| "object"
							| "null"
							| "integer"
							| "array"
						)[],
						enum: ["foo", "bar"],
					},
				},
			};
			const { container } = render(
				<TestSchemaForm schema={schema} values={{ name: "foo" }} />,
			);

			expect(container).toMatchSnapshot();
		});

		test("with default", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: {
						// sometimes pydantic creates a property with an undefined type
						type: undefined as unknown as (
							| "string"
							| "number"
							| "boolean"
							| "object"
							| "null"
							| "integer"
							| "array"
						)[],
						default: "foo",
					},
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(container).toMatchSnapshot();
		});
	});
});
