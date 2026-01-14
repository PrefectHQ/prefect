import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { SchemaFormInputStringFormatDateTime } from "./schema-form-input-string-format-datetime";

describe("SchemaFormInputStringFormatDateTime", () => {
	test("renders without crashing", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatDateTime
				value={undefined}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		expect(
			screen.getByRole("button", { name: /MM\/DD\/YYYY/i }),
		).toBeInTheDocument();
	});

	test("renders timezone selector", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatDateTime
				value={undefined}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		expect(
			screen.getByRole("button", { name: /select timezone/i }),
		).toBeInTheDocument();
	});

	test("displays datetime value when provided", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatDateTime
				value="2024-01-15T10:30:00-05:00"
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		const dateButton = screen.getByRole("button", { name: /01\/15\/2024/i });
		expect(dateButton).toBeInTheDocument();
	});

	test("has correct id attribute on datetime picker", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatDateTime
				value={undefined}
				onValueChange={onValueChange}
				id="my-custom-id"
			/>,
		);

		const dateButton = screen.getByRole("button", { name: /MM\/DD\/YYYY/i });
		expect(dateButton).toHaveAttribute("id", "my-custom-id");
	});
});
