import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { DateRangeIso } from "./date-range-picker";
import { DateRangePicker } from "./date-range-picker";

describe("DateRangePicker", () => {
	it("renders placeholder and allows selecting a range", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn<(value: DateRangeIso | undefined) => void>();
		render(
			<DateRangePicker
				value={undefined}
				onValueChange={onValueChange}
				defaultMonth={new Date(2025, 2)}
			/>,
		);

		// Open the popover
		await user.click(
			screen.getByRole("button", { name: /pick a date range/i }),
		);

		// Select two dates for the range
		await user.click(
			screen.getByRole("button", { name: /wednesday, march 5th, 2025/i }),
		);
		await user.click(
			screen.getByRole("button", { name: /thursday, march 13th, 2025/i }),
		);

		// Close popover
		await user.keyboard("{Escape}");

		// Button reflects the selected range
		expect(
			screen.getByRole("button", { name: /03\/05\/2025 - 03\/13\/2025/i }),
		).toBeVisible();

		// Callback received ISO values
		expect(onValueChange).toHaveBeenCalled();
		const last = onValueChange.mock.calls.at(-1)?.[0];
		expect(last?.from).toBeTruthy();
		expect(last?.to).toBeTruthy();
	});

	it("shows initial value when provided", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn<(value: DateRangeIso | undefined) => void>();
		render(
			<DateRangePicker
				value={{
					from: new Date(2025, 2, 5).toISOString(),
					to: new Date(2025, 2, 13).toISOString(),
				}}
				onValueChange={onValueChange}
				defaultMonth={new Date(2025, 2)}
			/>,
		);

		expect(
			screen.getByRole("button", { name: /03\/05\/2025 - 03\/13\/2025/i }),
		).toBeVisible();

		// Open and adjust end date
		await user.click(
			screen.getByRole("button", { name: /03\/05\/2025 - 03\/13\/2025/i }),
		);
		await user.click(
			screen.getByRole("button", { name: /friday, march 14th, 2025/i }),
		);
		await user.keyboard("{Escape}");

		expect(
			screen.getByRole("button", { name: /03\/05\/2025 - 03\/14\/2025/i }),
		).toBeVisible();
	});
});
