import { fireEvent, render, screen } from "@testing-library/react";
import type { SchemaObject } from "openapi-typescript";
import { act, useState } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import "@/mocks/mock-json-input";
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

	describe("object without properties (Dict type)", () => {
		test("auto-switches to JSON input for object with no properties", async () => {
			const spy = vi.fn();

			function Wrapper() {
				const [values, setValues] = useState<Record<string, unknown>>({});
				spy.mockImplementation((value: Record<string, unknown>) =>
					setValues(value),
				);

				const schema: SchemaObject = {
					type: "object",
					properties: {
						config: { type: "object" },
					},
				};

				return (
					<TestSchemaForm
						schema={schema}
						values={values}
						onValuesChange={spy}
						kinds={["json"]}
					/>
				);
			}

			render(<Wrapper />);

			// eslint-disable-next-line @typescript-eslint/require-await
			await act(async () => {
				vi.runAllTimers();
			});

			expect(spy).toHaveBeenCalledWith(
				expect.objectContaining({
					config: { __prefect_kind: "json" },
				}),
			);
		});

		test("auto-switches to JSON input for object with empty properties", async () => {
			const spy = vi.fn();

			function Wrapper() {
				const [values, setValues] = useState<Record<string, unknown>>({});
				spy.mockImplementation((value: Record<string, unknown>) =>
					setValues(value),
				);

				const schema: SchemaObject = {
					type: "object",
					properties: {
						config: { type: "object", properties: {} },
					},
				};

				return (
					<TestSchemaForm
						schema={schema}
						values={values}
						onValuesChange={spy}
						kinds={["json"]}
					/>
				);
			}

			render(<Wrapper />);

			// eslint-disable-next-line @typescript-eslint/require-await
			await act(async () => {
				vi.runAllTimers();
			});

			expect(spy).toHaveBeenCalledWith(
				expect.objectContaining({
					config: { __prefect_kind: "json" },
				}),
			);
		});

		test("renders JSON input after auto-switching", async () => {
			function Wrapper() {
				const [values, setValues] = useState<Record<string, unknown>>({});

				const schema: SchemaObject = {
					type: "object",
					properties: {
						config: { type: "object" },
					},
				};

				return (
					<TestSchemaForm
						schema={schema}
						values={values}
						onValuesChange={setValues}
						kinds={["json"]}
					/>
				);
			}

			render(<Wrapper />);

			// eslint-disable-next-line @typescript-eslint/require-await
			await act(async () => {
				vi.runAllTimers();
			});

			expect(screen.getByTestId("mock-json-input")).toBeInTheDocument();
		});

		test("preserves existing dict values in edit flows", async () => {
			const spy = vi.fn();

			function Wrapper() {
				const [values, setValues] = useState<Record<string, unknown>>({
					config: {
						__prefect_kind: "json",
						value: '{"region_name": "us-east-1"}',
					},
				});
				spy.mockImplementation((value: Record<string, unknown>) =>
					setValues(value),
				);

				const schema: SchemaObject = {
					type: "object",
					properties: {
						config: { type: "object" },
					},
				};

				return (
					<TestSchemaForm
						schema={schema}
						values={values}
						onValuesChange={spy}
						kinds={["json"]}
					/>
				);
			}

			render(<Wrapper />);

			// eslint-disable-next-line @typescript-eslint/require-await
			await act(async () => {
				vi.runAllTimers();
			});

			const overwroteWithEmptyJson = spy.mock.calls.some((call: unknown[]) => {
				const val = call[0] as Record<string, unknown> | undefined;
				if (!val?.config || typeof val.config !== "object") return false;
				const config = val.config as Record<string, unknown>;
				return config.__prefect_kind === "json" && !("value" in config);
			});
			expect(overwroteWithEmptyJson).toBe(false);
		});

		test("does not auto-switch for object with defined properties", async () => {
			const spy = vi.fn();

			function Wrapper() {
				const [values, setValues] = useState<Record<string, unknown>>({});
				spy.mockImplementation((value: Record<string, unknown>) =>
					setValues(value),
				);

				const schema: SchemaObject = {
					type: "object",
					properties: {
						config: {
							type: "object",
							properties: {
								name: { type: "string" },
							},
						},
					},
				};

				return (
					<TestSchemaForm
						schema={schema}
						values={values}
						onValuesChange={spy}
						kinds={["json"]}
					/>
				);
			}

			render(<Wrapper />);

			// eslint-disable-next-line @typescript-eslint/require-await
			await act(async () => {
				vi.runAllTimers();
			});

			const hasJsonKind = spy.mock.calls.some((call: unknown[]) => {
				const val = call[0] as Record<string, unknown> | undefined;
				return (
					val?.config !== undefined &&
					typeof val.config === "object" &&
					val.config !== null &&
					"__prefect_kind" in val.config
				);
			});
			expect(hasJsonKind).toBe(false);
		});
	});
});
