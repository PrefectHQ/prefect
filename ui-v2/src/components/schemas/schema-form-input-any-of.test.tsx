import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { SchemaObject } from "openapi-typescript";
import { useEffect, useState } from "react";
import { describe, expect, test, vi } from "vitest";
import "@/mocks/mock-json-input";
import { SchemaFormInputAnyOf } from "./schema-form-input-any-of";
import { SchemaFormProvider } from "./schema-form-provider";
import type { PrefectSchemaObject } from "./types/schemas";

const SECRET_LIKE_SCHEMA = {
	type: "object",
	properties: {
		value: {
			anyOf: [{ type: "string", format: "password" }, { type: "string" }, {}],
		},
	},
} as unknown as PrefectSchemaObject;

const SECRET_LIKE_PROPERTY = {
	anyOf: [{ type: "string", format: "password" }, { type: "string" }, {}],
} as unknown as SchemaObject & { anyOf: SchemaObject[] };

function renderWithSchemaContext(
	ui: React.ReactElement,
	schema = SECRET_LIKE_SCHEMA,
) {
	return render(
		<SchemaFormProvider schema={schema} kinds={[]}>
			{ui}
		</SchemaFormProvider>,
	);
}

describe("SchemaFormInputAnyOf", () => {
	test("renders tabs for anyOf definitions", () => {
		const onValueChange = vi.fn();

		renderWithSchemaContext(
			<SchemaFormInputAnyOf
				value={undefined}
				property={SECRET_LIKE_PROPERTY}
				onValueChange={onValueChange}
				errors={[]}
			/>,
		);

		expect(screen.getByRole("tab", { name: "password" })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: "str" })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: "Field" })).toBeInTheDocument();
	});

	test("tabs remain visible when value is a json prefect kind", () => {
		const onValueChange = vi.fn();
		const jsonValue = { __prefect_kind: "json", value: '{"key": "val"}' };

		renderWithSchemaContext(
			<SchemaFormInputAnyOf
				value={jsonValue}
				property={SECRET_LIKE_PROPERTY}
				onValueChange={onValueChange}
				errors={[]}
			/>,
		);

		expect(screen.getByRole("tab", { name: "password" })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: "str" })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: "Field" })).toBeInTheDocument();
	});

	test("tabs remain visible when value is a jinja prefect kind", () => {
		const onValueChange = vi.fn();
		const jinjaValue = {
			__prefect_kind: "jinja",
			template: "{{ flow_run.name }}",
		};

		renderWithSchemaContext(
			<SchemaFormInputAnyOf
				value={jinjaValue}
				property={SECRET_LIKE_PROPERTY}
				onValueChange={onValueChange}
				errors={[]}
			/>,
		);

		expect(screen.getByRole("tab", { name: "password" })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: "str" })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: "Field" })).toBeInTheDocument();
	});

	test("selects the correct tab for a json prefect kind value", () => {
		const onValueChange = vi.fn();
		const jsonValue = { __prefect_kind: "json", value: '{"key": "val"}' };

		renderWithSchemaContext(
			<SchemaFormInputAnyOf
				value={jsonValue}
				property={SECRET_LIKE_PROPERTY}
				onValueChange={onValueChange}
				errors={[]}
			/>,
		);

		const fieldTab = screen.getByRole("tab", { name: "Field" });
		expect(fieldTab).toHaveAttribute("aria-selected", "true");
	});

	test("can switch from Field tab back to password tab", async () => {
		const user = userEvent.setup();

		function Wrapper() {
			const [value, setValue] = useState<unknown>({
				__prefect_kind: "json",
				value: '{"key": "val"}',
			});

			return (
				<SchemaFormProvider schema={SECRET_LIKE_SCHEMA} kinds={[]}>
					<SchemaFormInputAnyOf
						value={value}
						property={SECRET_LIKE_PROPERTY}
						onValueChange={setValue}
						errors={[]}
					/>
				</SchemaFormProvider>
			);
		}

		render(<Wrapper />);

		const fieldTab = screen.getByRole("tab", { name: "Field" });
		expect(fieldTab).toHaveAttribute("aria-selected", "true");

		const passwordTab = screen.getByRole("tab", { name: "password" });
		await user.click(passwordTab);

		expect(passwordTab).toHaveAttribute("aria-selected", "true");
		expect(fieldTab).toHaveAttribute("aria-selected", "false");
	});

	test("can switch from password tab to Field tab and back", async () => {
		const user = userEvent.setup();

		function Wrapper() {
			const [value, setValue] = useState<unknown>(undefined);

			return (
				<SchemaFormProvider schema={SECRET_LIKE_SCHEMA} kinds={[]}>
					<SchemaFormInputAnyOf
						value={value}
						property={SECRET_LIKE_PROPERTY}
						onValueChange={setValue}
						errors={[]}
					/>
				</SchemaFormProvider>
			);
		}

		render(<Wrapper />);

		const passwordTab = screen.getByRole("tab", { name: "password" });
		const fieldTab = screen.getByRole("tab", { name: "Field" });

		expect(passwordTab).toHaveAttribute("aria-selected", "true");

		await user.click(fieldTab);
		expect(fieldTab).toHaveAttribute("aria-selected", "true");
		expect(screen.getByRole("tab", { name: "password" })).toBeInTheDocument();

		await user.click(screen.getByRole("tab", { name: "password" }));
		expect(screen.getByRole("tab", { name: "password" })).toHaveAttribute(
			"aria-selected",
			"true",
		);
	});

	test("reports null when switching to the None branch", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();

		const schema: PrefectSchemaObject = {
			type: "object",
			properties: {},
		};
		const property = {
			anyOf: [{ type: "string" }, { type: "null" }],
			default: "value.split(',')",
		} as SchemaObject & { anyOf: SchemaObject[] };

		function Wrapper() {
			const [value, setValue] = useState<unknown>("value.split(',')");

			onValueChange.mockImplementation((newValue: unknown) =>
				setValue(newValue),
			);

			return (
				<SchemaFormProvider schema={schema} kinds={[]}>
					<SchemaFormInputAnyOf
						value={value}
						property={property}
						onValueChange={onValueChange}
						errors={[]}
					/>
				</SchemaFormProvider>
			);
		}

		render(<Wrapper />);

		await user.click(screen.getByRole("tab", { name: "None" }));

		await waitFor(() => {
			expect(onValueChange).toHaveBeenLastCalledWith(null);
		});

		expect(screen.getByRole("tab", { name: "None" })).toHaveAttribute(
			"aria-selected",
			"true",
		);
	});

	test("keeps the None branch selected for an existing null value", async () => {
		const onValueChange = vi.fn();

		const schema: PrefectSchemaObject = {
			type: "object",
			properties: {},
		};
		const property = {
			anyOf: [{ type: "string" }, { type: "null" }],
			default: "value.split(',')",
		} as SchemaObject & { anyOf: SchemaObject[] };

		renderWithSchemaContext(
			<SchemaFormInputAnyOf
				value={null}
				property={property}
				onValueChange={onValueChange}
				errors={[]}
			/>,
			schema,
		);

		expect(screen.getByRole("tab", { name: "None" })).toHaveAttribute(
			"aria-selected",
			"true",
		);

		await waitFor(() => {
			expect(onValueChange).not.toHaveBeenCalled();
		});
	});

	test("selects the object branch for a record value when no branch declares properties", () => {
		const onValueChange = vi.fn();

		const schema: PrefectSchemaObject = {
			type: "object",
			properties: {},
		};
		const property = {
			anyOf: [{ type: "null" }, { type: "object", title: "dict" }],
			default: null,
		} as SchemaObject & { anyOf: SchemaObject[] };

		renderWithSchemaContext(
			<SchemaFormInputAnyOf
				value={{ retries: 2 }}
				property={property}
				onValueChange={onValueChange}
				errors={[]}
			/>,
			schema,
		);

		expect(screen.getByRole("tab", { name: "dict" })).toHaveAttribute(
			"aria-selected",
			"true",
		);
	});

	test("selects the first branch when the value matches no branch", () => {
		const onValueChange = vi.fn();

		const schema: PrefectSchemaObject = {
			type: "object",
			properties: {},
		};
		const property = {
			anyOf: [{ type: "string", title: "str" }, { type: "null" }],
		} as SchemaObject & { anyOf: SchemaObject[] };

		renderWithSchemaContext(
			<SchemaFormInputAnyOf
				value={{ unexpected: "value" }}
				property={property}
				onValueChange={onValueChange}
				errors={[]}
			/>,
			schema,
		);

		expect(screen.getByRole("tab", { name: "str" })).toHaveAttribute(
			"aria-selected",
			"true",
		);
	});

	test("selects the matching branch when a controlled value arrives after mount", async () => {
		const schema: PrefectSchemaObject = {
			type: "object",
			properties: {},
		};
		const property = {
			anyOf: [
				{ type: "string", format: "date", title: "Date" },
				{
					type: "string",
					title: "Relative date",
					enum: ["today", "prev_td"],
				},
			],
		} as SchemaObject & { anyOf: SchemaObject[] };

		function Wrapper() {
			const [value, setValue] = useState<unknown>(undefined);

			useEffect(() => {
				setValue("prev_td");
			}, []);

			return (
				<SchemaFormProvider schema={schema} kinds={[]}>
					<SchemaFormInputAnyOf
						value={value}
						property={property}
						onValueChange={setValue}
						errors={[]}
					/>
				</SchemaFormProvider>
			);
		}

		render(<Wrapper />);

		await waitFor(() => {
			expect(
				screen.getByRole("tab", { name: "Relative date" }),
			).toHaveAttribute("aria-selected", "true");
		});
	});
});
