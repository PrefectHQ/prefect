import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeAll, describe, expect, test, vi } from "vitest";
import { SchemaFormInputStringFormatDateTime } from "./schema-form-input-string-format-datetime";

describe("SchemaFormInputStringFormatDateTime", () => {
	beforeAll(mockPointerEvents);

	test.each([
		[
			"2024-01-15T15:30:00Z",
			"America/New_York",
			"America / New York",
			"2024-01-15T10:30:00-05:00",
		],
		[
			"2024-07-15T15:30:00Z",
			"America/New_York",
			"America / New York",
			"2024-07-15T11:30:00-04:00",
		],
		[
			"2024-01-15T15:30:00Z",
			"Asia/Katmandu",
			"Asia / Katmandu",
			"2024-01-15T21:15:00+05:45",
		],
		["2024-01-15T10:30:00-05:00", "UTC", "UTC", "2024-01-15T15:30:00Z"],
	])(
		"preserves the instant when changing %s to %s",
		async (value, timezone, label, expected) => {
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
			await user.type(screen.getByPlaceholderText("Search"), timezone);
			await user.click(await screen.findByRole("option", { name: label }));
			expect(onValueChange).toHaveBeenLastCalledWith(expected);
		},
	);

	test("changing timezone does not populate an unset datetime", async () => {
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
		await user.type(screen.getByPlaceholderText("Search"), "America/New_York");
		await user.click(
			await screen.findByRole("option", {
				name: "America / New York",
			}),
		);
		expect(onValueChange).not.toHaveBeenCalled();
	});

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
