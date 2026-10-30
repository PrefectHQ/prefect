import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
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

	test.each([
		{
			value: "2024-01-15T15:30:00Z",
			timezone: "America/New_York",
			search: "New York",
			option: /america \/ new york/i,
			expected: "2024-01-15T10:30:00-05:00",
		},
		{
			value: "2024-07-15T15:30:00Z",
			timezone: "America/New_York",
			search: "New York",
			option: /america \/ new york/i,
			expected: "2024-07-15T11:30:00-04:00",
		},
		{
			value: "2024-01-15T15:30:00Z",
			timezone: "Asia/Kathmandu",
			search: "Asia / Kat",
			option: /asia \/ kath?mandu/i,
			expected: "2024-01-15T21:15:00+05:45",
		},
		{
			value: "2024-01-15T10:30:00-05:00",
			timezone: "UTC",
			search: "UTC",
			option: /^utc$/i,
			expected: "2024-01-15T15:30:00Z",
		},
	])(
		"preserves the instant of $value when the timezone changes to $timezone",
		async ({ value, search, option, expected }) => {
			mockPointerEvents();
			const user = userEvent.setup();
			const onValueChange = vi.fn();

			render(
				<SchemaFormInputStringFormatDateTime
					value={value}
					onValueChange={onValueChange}
					id="test-id"
				/>,
			);

			await user.click(
				screen.getByRole("button", { name: /select timezone/i }),
			);
			await user.type(screen.getByPlaceholderText(/search/i), search);
			const [timezoneOption] = await screen.findAllByRole("option", {
				name: option,
			});
			await user.click(timezoneOption);

			expect(onValueChange).toHaveBeenCalledWith(expected);
			const [emittedValue] = onValueChange.mock.lastCall as [string];
			expect(new Date(emittedValue).toISOString()).toBe(
				new Date(value).toISOString(),
			);
		},
	);

	test("does not emit a value when the timezone changes without a value", async () => {
		mockPointerEvents();
		const user = userEvent.setup();
		const onValueChange = vi.fn();

		render(
			<SchemaFormInputStringFormatDateTime
				value={undefined}
				onValueChange={onValueChange}
				id="test-id"
			/>,
		);

		await user.click(screen.getByRole("button", { name: /select timezone/i }));
		await user.type(screen.getByPlaceholderText(/search/i), "New York");
		await user.click(
			await screen.findByRole("option", { name: /america \/ new york/i }),
		);

		expect(onValueChange).not.toHaveBeenCalled();
	});
});
