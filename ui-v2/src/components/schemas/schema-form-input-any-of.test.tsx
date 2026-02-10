import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { SchemaObject } from "openapi-typescript";
import { useState } from "react";
import { describe, expect, test, vi } from "vitest";
import "@/mocks/mock-json-input";
import { SchemaFormInputAnyOf } from "./schema-form-input-any-of";
import { SchemaFormProvider } from "./schema-form-provider";

const SECRET_LIKE_SCHEMA: SchemaObject = {
	type: "object",
	properties: {
		value: {
			anyOf: [{ type: "string", format: "password" }, { type: "string" }, {}],
		},
	},
};

const SECRET_LIKE_PROPERTY: SchemaObject & {
	anyOf: SchemaObject[];
} = {
	anyOf: [{ type: "string", format: "password" }, { type: "string" }, {}],
};

function renderWithSchemaContext(
	ui: React.ReactElement,
	schema: SchemaObject = SECRET_LIKE_SCHEMA,
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
});
