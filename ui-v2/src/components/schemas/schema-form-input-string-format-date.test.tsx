import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { SchemaFormInputStringFormatDate } from "./schema-form-input-string-format-date";

describe("SchemaFormInputStringFormatDate", () => {
	test("renders without crashing", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatDate
				value={undefined}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		expect(
			screen.getByRole("button", { name: /Pick a date/i }),
		).toBeInTheDocument();
	});

	test("displays date value when provided", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatDate
				value="2024-01-15"
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		expect(
			screen.getByRole("button", { name: /January 15th, 2024/i }),
		).toBeInTheDocument();
	});

	test("has correct id attribute on date picker", () => {
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatDate
				value={undefined}
				onValueChange={onValueChange}
				id="my-custom-id"
			/>,
		);

		const dateButton = screen.getByRole("button", { name: /Pick a date/i });
		expect(dateButton).toHaveAttribute("id", "my-custom-id");
	});

	test("can type a date manually", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatDate
				value={undefined}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		await user.click(screen.getByRole("button", { name: /Pick a date/i }));

		const input = screen.getByLabelText("Date (yyyy-MM-dd)");
		await user.type(input, "2024-01-15");

		expect(onValueChange).toHaveBeenLastCalledWith("2024-01-15");
	});

	test("can select a date from the calendar", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatDate
				value={undefined}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		await user.click(screen.getByRole("button", { name: /Pick a date/i }));

		await user.click(
			screen.getByRole("button", { name: /wednesday, july 15th, 2026/i }),
		);
		await user.keyboard("{Escape}");

		expect(
			screen.getByRole("button", { name: /July 15th, 2026/i }),
		).toBeVisible();
		expect(onValueChange).toHaveBeenLastCalledWith("2026-07-15");
	});
});
