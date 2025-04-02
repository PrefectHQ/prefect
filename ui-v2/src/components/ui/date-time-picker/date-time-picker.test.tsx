import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DateTimePicker } from "./date-time-picker";

describe("DateTimePicker", () => {
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
