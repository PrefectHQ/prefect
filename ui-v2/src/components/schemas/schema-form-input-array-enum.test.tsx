import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import type { SchemaObject } from "openapi-typescript";
import { useState } from "react";
import { beforeAll, describe, expect, test, vi } from "vitest";
import type { SchemaFormProps } from "./schema-form";
import { SchemaForm } from "./schema-form";

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

describe("SchemaFormInputArray enum", () => {
	beforeAll(mockPointerEvents);

	test("clearing all selections sends [] instead of omitting the field", async () => {
		const user = userEvent.setup();
		const spy = vi.fn();

		function Wrapper() {
			const [values, setValues] = useState<Record<string, unknown>>({
				tags: ["foo"],
			});
			spy.mockImplementation((value: Record<string, unknown>) =>
				setValues(value),
			);

			const schema: SchemaObject = {
				type: "object",
				properties: {
					tags: {
						type: "array",
						title: "Tags",
						items: { type: "string", enum: ["foo", "bar", "baz"] },
					},
				},
			};

			return (
				<TestSchemaForm schema={schema} values={values} onValuesChange={spy} />
			);
		}

		render(<Wrapper />);

		// Open the combobox and deselect the only selected item
		await user.click(screen.getByRole("button", { name: /select tags/i }));
		await user.click(screen.getByRole("option", { name: /^foo$/i }));

		// tags key must be [] not omitted — omitting it would cause the server
		// to fall back to the deployment's stored default instead of empty list
		await waitFor(() => {
			expect(spy).toHaveBeenLastCalledWith({ tags: [] });
		});
	});

	test("clearing all selections omits the field when it is required", async () => {
		const user = userEvent.setup();
		const spy = vi.fn();

		function Wrapper() {
			const [values, setValues] = useState<Record<string, unknown>>({
				tags: ["foo"],
			});
			spy.mockImplementation((value: Record<string, unknown>) =>
				setValues(value),
			);

			const schema: SchemaObject = {
				type: "object",
				required: ["tags"],
				properties: {
					tags: {
						type: "array",
						title: "Tags",
						items: { type: "string", enum: ["foo", "bar", "baz"] },
					},
				},
			};

			return (
				<TestSchemaForm schema={schema} values={values} onValuesChange={spy} />
			);
		}

		render(<Wrapper />);

		await user.click(screen.getByRole("button", { name: /select tags/i }));
		await user.click(screen.getByRole("option", { name: /^foo$/i }));

		// an empty array satisfies json schema's "required" check, so the field is
		// omitted instead to surface a "required property" validation error
		await waitFor(() => {
			expect(spy).toHaveBeenLastCalledWith({});
		});
	});

	test("clearing all selections sends [] when a required field allows minItems 0", async () => {
		const user = userEvent.setup();
		const spy = vi.fn();

		function Wrapper() {
			const [values, setValues] = useState<Record<string, unknown>>({
				tags: ["foo"],
			});
			spy.mockImplementation((value: Record<string, unknown>) =>
				setValues(value),
			);

			const schema: SchemaObject = {
				type: "object",
				required: ["tags"],
				properties: {
					tags: {
						type: "array",
						title: "Tags",
						minItems: 0,
						items: { type: "string", enum: ["foo", "bar", "baz"] },
					},
				},
			};

			return (
				<TestSchemaForm schema={schema} values={values} onValuesChange={spy} />
			);
		}

		render(<Wrapper />);

		await user.click(screen.getByRole("button", { name: /select tags/i }));
		await user.click(screen.getByRole("option", { name: /^foo$/i }));

		await waitFor(() => {
			expect(spy).toHaveBeenLastCalledWith({ tags: [] });
		});
	});

	test("clearing all selections sends [] for an optional constrained array", async () => {
		const user = userEvent.setup();
		const spy = vi.fn();

		function Wrapper() {
			const [values, setValues] = useState<Record<string, unknown>>({
				tags: ["foo"],
			});
			spy.mockImplementation((value: Record<string, unknown>) =>
				setValues(value),
			);

			const schema: SchemaObject = {
				type: "object",
				properties: {
					tags: {
						type: "array",
						title: "Tags",
						minItems: 1,
						items: { type: "string", enum: ["foo", "bar", "baz"] },
					},
				},
			};

			return (
				<TestSchemaForm schema={schema} values={values} onValuesChange={spy} />
			);
		}

		render(<Wrapper />);

		await user.click(screen.getByRole("button", { name: /select tags/i }));
		await user.click(screen.getByRole("option", { name: /^foo$/i }));

		await waitFor(() => {
			expect(spy).toHaveBeenLastCalledWith({ tags: [] });
		});
	});

	test("clearing a required anyOf array honors the active branch minItems", async () => {
		const user = userEvent.setup();
		const spy = vi.fn();

		function Wrapper() {
			const [values, setValues] = useState<Record<string, unknown>>({
				tags: ["foo"],
			});
			spy.mockImplementation((value: Record<string, unknown>) =>
				setValues(value),
			);

			const tagsProperty = {
				title: "Tags",
				anyOf: [
					{
						type: "array",
						minItems: 0,
						items: { type: "string", enum: ["foo", "bar", "baz"] },
					},
					{ type: "null" },
				],
			} as SchemaObject & { anyOf: SchemaObject[] };
			const schema: SchemaObject = {
				type: "object",
				required: ["tags"],
				properties: {
					tags: tagsProperty,
				},
			};

			return (
				<TestSchemaForm schema={schema} values={values} onValuesChange={spy} />
			);
		}

		render(<Wrapper />);

		await user.click(screen.getByRole("button", { name: /remove foo tag/i }));

		await waitFor(() => {
			expect(spy).toHaveBeenLastCalledWith({ tags: [] });
		});
	});

	test("omits a required array that is initially empty", async () => {
		const spy = vi.fn();

		function Wrapper() {
			const [values, setValues] = useState<Record<string, unknown>>({
				tags: [],
			});
			spy.mockImplementation((value: Record<string, unknown>) =>
				setValues(value),
			);

			const schema: SchemaObject = {
				type: "object",
				required: ["tags"],
				properties: {
					tags: {
						type: "array",
						title: "Tags",
						items: { type: "string", enum: ["foo", "bar", "baz"] },
					},
				},
			};

			return (
				<TestSchemaForm schema={schema} values={values} onValuesChange={spy} />
			);
		}

		render(<Wrapper />);

		await waitFor(() => {
			expect(spy).toHaveBeenLastCalledWith({});
		});
	});
});
