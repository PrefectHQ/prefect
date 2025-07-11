import { fireEvent, render, screen } from "@testing-library/react";
import type { SchemaObject } from "openapi-typescript";
import { act, useState } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
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

beforeEach(() => {
	vi.useFakeTimers();
});

afterEach(() => {
	vi.useRealTimers();
});

describe("property.type", () => {
	describe("string", () => {
		test("base", async () => {
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

			render(<Wrapper />);

			const input = screen.getByRole("textbox");

			fireEvent.change(input, { target: { value: "bar" } });

			// fixes warning: "An update to Wrapper inside a test was not wrapped in act(...)"
			// eslint-disable-next-line @typescript-eslint/require-await
			await act(async () => {
				vi.runAllTimers();
			});

			expect(spy).toHaveBeenCalledTimes(1);
			expect(spy).toHaveBeenCalledWith({ name: "bar" });
		});
	});

	test("base with default value", async () => {
		const spy = vi.fn();

		function Wrapper() {
			const [values, setValues] = useState({});
			spy.mockImplementation((value: Record<string, unknown>) =>
				setValues(value),
			);

			const schema: SchemaObject = {
				type: "object",
				properties: {
					name: { type: "string", default: "John Doe" },
				},
			};

			return (
				<TestSchemaForm schema={schema} values={values} onValuesChange={spy} />
			);
		}

		render(<Wrapper />);

		// fixes warning: "An update to Wrapper inside a test was not wrapped in act(...)"
		// eslint-disable-next-line @typescript-eslint/require-await
		await act(async () => {
			vi.runAllTimers();
		});

		expect(spy).toHaveBeenCalledTimes(1);
		expect(spy).toHaveBeenCalledWith({ name: "John Doe" });
	});
});
