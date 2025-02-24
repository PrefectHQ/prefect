import { fireEvent } from "@testing-library/react";
import { render } from "@testing-library/react";
import { SchemaObject } from "openapi-typescript";
import { act, useState } from "react";
import { describe, test, vi } from "vitest";
import { expect } from "vitest";
import { SchemaForm } from "./schema-form";
import { SchemaFormProps } from "./schema-form";

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
		test("", async () => {
			vi.useFakeTimers();
			const spy = vi.fn();

			function Wrapper() {
				const [values, setValues] = useState({});
				spy.mockImplementation((value: Record<string, unknown>) =>
					setValues(value),
				);

				const schema: SchemaObject = {
					type: "object",
					properties: {
						name: { type: "string" },
					},
				};

				return (
					<TestSchemaForm
						schema={schema}
						values={values}
						onValuesChange={spy}
					/>
				);
			}

			const { container } = render(<Wrapper />);

			const input = container.querySelector("textarea");

			if (!input) {
				throw new Error("input not found");
			}

			fireEvent.change(input, { target: { value: "bar" } });

			// fixes warning: "An update to Wrapper inside a test was not wrapped in act(...)"
			// eslint-disable-next-line @typescript-eslint/require-await
			await act(async () => {
				vi.runAllTimers();
			});

			expect(spy).toHaveBeenCalledTimes(1);
			expect(spy).toHaveBeenCalledWith({ name: "bar" });

			vi.useRealTimers();
		});
	});
});
