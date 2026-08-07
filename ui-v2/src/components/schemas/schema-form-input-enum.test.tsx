import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { useState } from "react";
import { beforeAll, describe, expect, test, vi } from "vitest";
import type { SchemaFormProps } from "./schema-form";
import { SchemaForm } from "./schema-form";
import type { PrefectSchemaObject } from "./types/schemas";

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

// Array property has a title so the combobox trigger reads "Select Colors"
const multiEnumSchema: PrefectSchemaObject = {
	type: "object",
	properties: {
		colors: {
			title: "Colors",
			type: "array",
			items: { type: "string", enum: ["foo", "bar", "baz"] },
		},
	},
};

const singleEnumSchema: PrefectSchemaObject = {
	type: "object",
	properties: {
		name: { type: "string", title: "Name", enum: ["foo", "bar", "baz"] },
	},
};

describe("SchemaFormInputEnum", () => {
	beforeAll(mockPointerEvents);

	describe("multiple select — chips", () => {
		test("renders chips for each selected value", () => {
			render(
				<TestSchemaForm
					schema={multiEnumSchema}
					values={{ colors: ["foo", "bar"] }}
				/>,
			);

			expect(screen.getByTitle("foo")).toBeInTheDocument();
			expect(screen.getByTitle("bar")).toBeInTheDocument();
		});

		test("does not render chips when values array is empty", () => {
			render(
				<TestSchemaForm schema={multiEnumSchema} values={{ colors: [] }} />,
			);

			expect(
				screen.queryByRole("button", { name: /remove .* tag/i }),
			).not.toBeInTheDocument();
		});

		test("does not render chips when values are undefined", () => {
			render(<TestSchemaForm schema={multiEnumSchema} values={{}} />);

			expect(
				screen.queryByRole("button", { name: /remove .* tag/i }),
			).not.toBeInTheDocument();
		});

		test("clicking remove on a chip removes that value", async () => {
			const user = userEvent.setup();
			const spy = vi.fn();

			function Wrapper() {
				const [values, setValues] = useState<Record<string, unknown>>({
					colors: ["foo", "bar"],
				});
				spy.mockImplementation((v: Record<string, unknown>) => setValues(v));

				return (
					<TestSchemaForm
						schema={multiEnumSchema}
						values={values}
						onValuesChange={spy}
					/>
				);
			}

			render(<Wrapper />);

			await user.click(screen.getByRole("button", { name: "Remove foo tag" }));

			await waitFor(() => {
				expect(spy).toHaveBeenLastCalledWith({ colors: ["bar"] });
			});
		});

		test("removing the last chip results in an empty array", async () => {
			const user = userEvent.setup();
			const spy = vi.fn();

			function Wrapper() {
				const [values, setValues] = useState<Record<string, unknown>>({
					colors: ["foo"],
				});
				spy.mockImplementation((v: Record<string, unknown>) => setValues(v));

				return (
					<TestSchemaForm
						schema={multiEnumSchema}
						values={values}
						onValuesChange={spy}
					/>
				);
			}

			render(<Wrapper />);

			await user.click(screen.getByRole("button", { name: "Remove foo tag" }));

			await waitFor(() => {
				expect(spy).toHaveBeenLastCalledWith({ colors: [] });
			});
		});

		test("selecting a value from the combobox adds a chip", async () => {
			const user = userEvent.setup();
			const spy = vi.fn();

			function Wrapper() {
				const [values, setValues] = useState<Record<string, unknown>>({
					colors: [],
				});
				spy.mockImplementation((v: Record<string, unknown>) => setValues(v));

				return (
					<TestSchemaForm
						schema={multiEnumSchema}
						values={values}
						onValuesChange={spy}
					/>
				);
			}

			render(<Wrapper />);

			await user.click(screen.getByRole("button", { name: /select colors/i }));

			await waitFor(() => {
				expect(screen.getByRole("option", { name: "foo" })).toBeVisible();
			});

			await user.click(screen.getByRole("option", { name: "foo" }));

			await waitFor(() => {
				expect(spy).toHaveBeenLastCalledWith({ colors: ["foo"] });
			});
		});

		test("selecting an already-selected value from the combobox removes it", async () => {
			const user = userEvent.setup();
			const spy = vi.fn();

			function Wrapper() {
				const [values, setValues] = useState<Record<string, unknown>>({
					colors: ["foo", "bar"],
				});
				spy.mockImplementation((v: Record<string, unknown>) => setValues(v));

				return (
					<TestSchemaForm
						schema={multiEnumSchema}
						values={values}
						onValuesChange={spy}
					/>
				);
			}

			render(<Wrapper />);

			await user.click(screen.getByRole("button", { name: /select colors/i }));

			await waitFor(() => {
				expect(screen.getByRole("option", { name: "foo" })).toBeVisible();
			});

			await user.click(screen.getByRole("option", { name: "foo" }));

			await waitFor(() => {
				expect(spy).toHaveBeenLastCalledWith({ colors: ["bar"] });
			});
		});
	});

	describe("single select — no chips", () => {
		test("does not render chips for single-select enum", () => {
			render(
				<TestSchemaForm schema={singleEnumSchema} values={{ name: "foo" }} />,
			);

			expect(
				screen.queryByRole("button", { name: /remove .* tag/i }),
			).not.toBeInTheDocument();
		});

		test("shows the selected label in the combobox trigger", () => {
			render(
				<TestSchemaForm schema={singleEnumSchema} values={{ name: "foo" }} />,
			);

			expect(
				screen.getByRole("button", { name: /select name/i }),
			).toHaveTextContent("foo");
		});

		test("selecting a value calls onValuesChange with the new value", async () => {
			const user = userEvent.setup();
			const spy = vi.fn();

			function Wrapper() {
				const [values, setValues] = useState<Record<string, unknown>>({});
				spy.mockImplementation((v: Record<string, unknown>) => setValues(v));

				return (
					<TestSchemaForm
						schema={singleEnumSchema}
						values={values}
						onValuesChange={spy}
					/>
				);
			}

			render(<Wrapper />);

			await user.click(screen.getByRole("button", { name: /select name/i }));

			await waitFor(() => {
				expect(screen.getByRole("option", { name: "bar" })).toBeVisible();
			});

			await user.click(screen.getByRole("option", { name: "bar" }));

			await waitFor(() => {
				expect(spy).toHaveBeenLastCalledWith({ name: "bar" });
			});
		});
	});
});
