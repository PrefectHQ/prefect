import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { SchemaFormInputStringFormatTimeDelta } from "./schema-form-input-string-format-time-delta";

describe("SchemaFormInputStringFormatTimeDelta", () => {
	test("renders without crashing", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatTimeDelta
				value={undefined}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		expect(screen.getByRole("spinbutton")).toBeInTheDocument();
	});

	test("displays the value in the input", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatTimeDelta
				value="3600"
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const input = screen.getByRole("spinbutton");
		expect(input).toHaveValue(3600);
	});

	test("calls onValueChange with string value when user types", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatTimeDelta
				value={undefined}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const input = screen.getByRole("spinbutton");
		fireEvent.change(input, { target: { value: "7200" } });

		expect(onValueChange).toHaveBeenCalledWith("7200");
	});

	test("calls onValueChange with undefined when input is cleared", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatTimeDelta
				value="3600"
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const input = screen.getByRole("spinbutton");
		fireEvent.change(input, { target: { value: "" } });

		expect(onValueChange).toHaveBeenCalledWith(undefined);
	});

	test("handles undefined value", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatTimeDelta
				value={undefined}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const input = screen.getByRole("spinbutton");
		expect(input).toHaveValue(null);
	});

	test("has correct placeholder text", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatTimeDelta
				value={undefined}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const input = screen.getByPlaceholderText("Duration in seconds");
		expect(input).toBeInTheDocument();
	});

	test("has correct id attribute", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatTimeDelta
				value={undefined}
				onValueChange={onValueChange}
				id="my-custom-id"
			/>,
		);

		const input = screen.getByRole("spinbutton");
		expect(input).toHaveAttribute("id", "my-custom-id");
	});
});
