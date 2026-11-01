import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DateTimePicker } from "./date-time-picker";

describe("DateTimePicker", () => {
	it("aligns the popover to the start of the input", async () => {
		const user = userEvent.setup();
		render(<DateTimePicker value={undefined} onValueChange={vi.fn()} />);
		await user.click(screen.getByRole("button"));
		expect(screen.getByRole("dialog")).toHaveAttribute("data-align", "start");
	});

	it.each([0, 11, 12, 23])(
		"keeps the date when repeatedly selecting AM or PM from hour %i",
		async (hour) => {
			const user = userEvent.setup();
			const onValueChange = vi.fn<(value: string | undefined) => void>();
			render(
				<DateTimePicker
					value={new Date(2026, 9, 28, hour, 25).toISOString()}
					onValueChange={onValueChange}
				/>,
			);
			await user.click(screen.getByRole("button"));

			for (const period of ["PM", "PM", "AM", "AM"]) {
				await user.click(screen.getByRole("button", { name: period }));
				const expected = new Date(
					2026,
					9,
					28,
					(hour % 12) + (period === "PM" ? 12 : 0),
					25,
				);
				expect(new Date(onValueChange.mock.lastCall?.[0] ?? "")).toEqual(
					expected,
				);
				expect(
					screen.getByRole("button", {
						name: new RegExp(
							`10/28/2026 ${String(hour % 12 || 12).padStart(2, "0")}:25 ${period}`,
							"i",
						),
					}),
				).toBeVisible();
			}
		},
	);

	it("able to select a date and time", async () => {
		// Setup
		const MOCK_TIME_ISO = "2025-03-05T00:00:36.787Z";
		const user = userEvent.setup();
		const mockOnValueChange = vi.fn();
		render(
			<DateTimePicker
				value={MOCK_TIME_ISO}
				onValueChange={mockOnValueChange}
				defaultMonth={new Date(2025, 2)}
			/>,
		);

		// Act
		await user.click(
			screen.getByRole("button", { name: /03\/05\/2025 12:00 am/i }),
		);

		await user.click(
			screen.getByRole("button", { name: /thursday, march 13th, 2025/i }),
		);
		await user.keyboard("{Escape}");

		// Assert
		expect(
			screen.getByRole("button", { name: /03\/13\/2025 12:00 am/i }),
		).toBeVisible();
	});
});
