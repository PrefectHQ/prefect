import { fireEvent, render, screen } from "@testing-library/react";
import type { ReferenceObject, SchemaObject } from "openapi-typescript";
import { describe, expect, it, vi } from "vitest";
import { SchemaFormInputAnyOf } from "./schema-form-input-any-of";
import { SchemaFormProvider } from "./schema-form-provider";

const MyModel: SchemaObject = {
	type: "object",
	properties: {
		shared_parameter: { type: "string" },
		unique_1: { type: "integer" },
	},
	required: ["shared_parameter", "unique_1"],
};

const MyModel2: SchemaObject = {
	type: "object",
	properties: {
		shared_parameter: { type: "string" },
		unique_2: { type: "number" },
	},
	required: ["shared_parameter", "unique_2"],
};

const property: SchemaObject & { anyOf: (SchemaObject | ReferenceObject)[] } = {
	type: "object",
	anyOf: [MyModel, MyModel2],
};



describe("SchemaFormInputAnyOf", () => {
	it("renders the correct fields for each model and preserves shared parameter values", () => {
		let value: Record<string, unknown> = {
			shared_parameter: "foo",
			unique_1: 1,
		};
		const handleChange = vi.fn((v: unknown) => {
			value = v as Record<string, unknown>;
		});

		render(
			<SchemaFormProvider schema={property} kinds={["json"]}>
				<SchemaFormInputAnyOf
					value={value}
					property={property}
					onValueChange={handleChange}
					errors={[]}
				/>
			</SchemaFormProvider>,
		);

		expect(screen.getByLabelText(/str/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/int/i)).toBeInTheDocument();
		expect(screen.queryByLabelText(/float/i)).not.toBeInTheDocument();

		fireEvent.click(screen.getAllByRole("radio", { name: /dict/i })[1]);

		expect(screen.getByLabelText(/str/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/float/i)).toBeInTheDocument();
		expect(screen.queryByLabelText(/int/i)).not.toBeInTheDocument();

		expect(handleChange).toHaveBeenCalled();
	});

	it("does not render blank form and checks numeric field values when switching between models with overlapping parameters", () => {
		let value: Record<string, unknown> = {
			shared_parameter: "test",
			unique_1: 42,
		};
		const handleChange = vi.fn((v: unknown) => {
			value = v as Record<string, unknown>;
		});

		render(
			<SchemaFormProvider schema={property} kinds={["json"]}>
				<SchemaFormInputAnyOf
					value={value}
					property={property}
					onValueChange={handleChange}
					errors={[]}
				/>
			</SchemaFormProvider>,
		);
		const strInput = screen.getByLabelText(/str/i);
		const intInput = screen.getByLabelText(/int/i);
		expect(strInput).toHaveValue("test");
		expect(intInput).toHaveDisplayValue("42");

		fireEvent.click(screen.getAllByRole("radio", { name: /dict/i })[1]);

		const strInputAfter = screen.getByLabelText(/str/i);
		const floatInput = screen.getByLabelText(/float/i);
		expect(strInputAfter).toHaveValue("test");
		expect(floatInput).toHaveDisplayValue("");
	});
});
