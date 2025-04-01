"2025-03-05T23:50:36.787Z";

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
			/>,
		);

		// Act
		await user.click(
			screen.getByRole("button", { name: /03\/05\/2025 12:00 am/i }),
		);

		// Click on Thursday April 13th - the calendar displays April by default
		await user.click(
			screen.getByRole("button", { name: /sunday, april 13th, 2025/i }),
		);
		await user.keyboard("{Escape}");

		// Assert with the correct format that matches the component's actual output
		expect(
			screen.getByRole("button", { name: /04\/13\/2025 12:00 AM/i }),
		).toBeVisible();
	});
});
