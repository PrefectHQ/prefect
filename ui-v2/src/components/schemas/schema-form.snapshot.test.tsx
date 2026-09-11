import { render } from "@testing-library/react";
import type { SchemaObject } from "openapi-typescript";
import { describe, expect, test } from "vitest";
import "@/mocks/mock-json-input";
import { SchemaForm, type SchemaFormProps } from "./schema-form";

function normalizeGeneratedIds(container: HTMLElement): HTMLElement {
	const clone = container.cloneNode(true) as HTMLElement;
	const normalizedIds = new Map<string, string>();

	for (const element of [clone, ...clone.querySelectorAll("*")]) {
		for (const attribute of element.attributes) {
			attribute.value = attribute.value.replace(
				/(?:radix-)?_r_[a-z0-9]+_/g,
				(id) => {
					const normalizedId =
						normalizedIds.get(id) ?? `generated-id-${normalizedIds.size}`;
					normalizedIds.set(id, normalizedId);
					return normalizedId;
				},
			);
		}
	}

	return clone;
}

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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("with default", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", default: "foo" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("format:date", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", format: "date" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("format:date with default", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", format: "date", default: "2024-01-01" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("format:date-time", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", format: "date-time" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("format:json-string", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", format: "json-string" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("enum", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", enum: ["foo", "bar"] },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("enum with default", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", enum: ["foo", "bar"], default: "foo" },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("with default", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "number", default: 123.45 },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("enum", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "number", enum: [1, 2.5, 3.9] },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("with default", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "number", default: 123 },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("enum", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "number", enum: [1, 2, 3] },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("with default", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "boolean", default: true },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("enum", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "boolean", enum: [true, false] },
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
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

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});
	});

	describe("array", () => {
		test("base", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					items: {
						type: "array",
						items: { type: "string" },
					},
				},
			};
			const { container } = render(<TestSchemaForm schema={schema} />);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("with values - drag handles visible", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					items: {
						type: "array",
						items: { type: "string" },
					},
				},
			};
			const { container } = render(
				<TestSchemaForm
					schema={schema}
					values={{ items: ["foo", "bar", "baz"] }}
				/>,
			);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("with prefixItems - no drag handles on prefix items", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					items: {
						type: "array",
						prefixItems: [
							{ type: "string", title: "First" },
							{ type: "boolean", title: "Second" },
						],
						items: { type: "string" },
					},
				},
			};
			const { container } = render(
				<TestSchemaForm
					schema={schema}
					values={{ items: ["prefix1", true, "regular1", "regular2"] }}
				/>,
			);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});

		test("with enum items", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					items: {
						type: "array",
						items: { type: "string", enum: ["foo", "bar", "baz"] },
					},
				},
			};
			const { container } = render(
				<TestSchemaForm schema={schema} values={{ items: ["foo", "bar"] }} />,
			);

			expect(normalizeGeneratedIds(container)).toMatchSnapshot();
		});
	});
});
