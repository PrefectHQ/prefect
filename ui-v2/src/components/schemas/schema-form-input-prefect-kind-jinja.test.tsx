import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import "@/mocks/mock-json-input";
import { SchemaFormInputPrefectKindJinja } from "./schema-form-input-prefect-kind-jinja";

describe("SchemaFormInputPrefectKindJinja", () => {
	test("renders without crashing", () => {
		const value = { __prefect_kind: "jinja" as const, template: undefined };
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputPrefectKindJinja
				value={value}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		expect(screen.getByTestId("mock-json-input")).toBeInTheDocument();
	});

	test("displays the template value in the input", () => {
		const value = {
			__prefect_kind: "jinja" as const,
			template: "{{ flow_run.name }}",
		};
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputPrefectKindJinja
				value={value}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const input = screen.getByTestId("mock-json-input");
		expect(input).toHaveValue("{{ flow_run.name }}");
	});

	test("calls onValueChange with correct structure when user types", () => {
		const value = { __prefect_kind: "jinja" as const, template: undefined };
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputPrefectKindJinja
				value={value}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const input = screen.getByTestId("mock-json-input");
		fireEvent.change(input, { target: { value: "{{ task_run.id }}" } });

		expect(onValueChange).toHaveBeenCalledWith({
			__prefect_kind: "jinja",
			template: "{{ task_run.id }}",
		});
	});

	test("handles empty string by setting template to undefined", () => {
		const value = {
			__prefect_kind: "jinja" as const,
			template: "{{ flow_run.name }}",
		};
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputPrefectKindJinja
				value={value}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const input = screen.getByTestId("mock-json-input");
		fireEvent.change(input, { target: { value: "" } });

		expect(onValueChange).toHaveBeenCalledWith({
			__prefect_kind: "jinja",
			template: undefined,
		});
	});

	test("handles undefined template value", () => {
		const value = { __prefect_kind: "jinja" as const, template: undefined };
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputPrefectKindJinja
				value={value}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const input = screen.getByTestId("mock-json-input");
		expect(input).toHaveValue("");
	});

	test("preserves __prefect_kind: jinja in the value", () => {
		const value = { __prefect_kind: "jinja" as const, template: "initial" };
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputPrefectKindJinja
				value={value}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const input = screen.getByTestId("mock-json-input");
		fireEvent.change(input, { target: { value: "updated" } });

		expect(onValueChange).toHaveBeenCalledWith(
			expect.objectContaining({
				__prefect_kind: "jinja",
			}),
		);
	});
});
