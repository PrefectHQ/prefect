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
});
