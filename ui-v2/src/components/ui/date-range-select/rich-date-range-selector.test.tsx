import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	type DateRangeSelectValue,
	RichDateRangeSelector,
} from "./rich-date-range-selector";

function Controlled({
	initialValue = null,
	onExternalChange,
}: {
	initialValue?: DateRangeSelectValue;
	onExternalChange?: (v: DateRangeSelectValue) => void;
}) {
	const [val, setVal] = React.useState<DateRangeSelectValue>(initialValue);
	return (
		<RichDateRangeSelector
			value={val}
			onValueChange={(v) => {
				setVal(v);
				onExternalChange?.(v);
			}}
		/>
	);
}

// Type guard to satisfy type-aware lint rules
function isRange(
	value: DateRangeSelectValue,
): value is Extract<DateRangeSelectValue, { type: "range" }> {
	return Boolean(
		value &&
			typeof value === "object" &&
			"type" in value &&
			value.type === "range",
	);
}

describe("RichDateRangeSelector", () => {
	let user: ReturnType<typeof userEvent.setup>;
	beforeEach(() => {
		// Use fake timers that auto-advance so Radix + userEvent don't stall
		vi.useFakeTimers({ shouldAdvanceTime: true });
		vi.setSystemTime(new Date("2025-01-15T12:34:56.789Z"));
		user = userEvent.setup({
			advanceTimers: vi.advanceTimersByTimeAsync.bind(vi),
		});
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("shows placeholder and opens options", async () => {
		const onChange = vi.fn();
		render(<RichDateRangeSelector value={null} onValueChange={onChange} />);
		expect(screen.getByText("Select a time span")).toBeInTheDocument();
		await user.click(
			screen.getByRole("button", { name: /select a time span/i }),
		);
		expect(
			await screen.findByRole("button", { name: /Past hour/i }),
		).toBeInTheDocument();
	});

	it("applies a relative preset (Past hour)", async () => {
		const onChange = vi.fn();
		render(<Controlled onExternalChange={onChange} />);
		await user.click(
			screen.getByRole("button", { name: /select a time span/i }),
		);
		await user.click(await screen.findByRole("button", { name: /Past hour/i }));
		expect(onChange).toHaveBeenCalled();
		// Placeholder should no longer be visible on the trigger
		expect(screen.queryByText("Select a time span")).not.toBeInTheDocument();
	});

	it("applies Today period", async () => {
		const onChange = vi.fn();
		render(<RichDateRangeSelector value={null} onValueChange={onChange} />);
		await user.click(
			screen.getByRole("button", { name: /select a time span/i }),
		);
		await user.click(await screen.findByRole("button", { name: /^Today$/ }));
		expect(onChange).toHaveBeenCalledWith({ type: "period", period: "Today" });
	});

	it("relative view filters by query and applies selection", async () => {
		const onChange = vi.fn();
		render(<Controlled onExternalChange={onChange} />);
		await user.click(
			screen.getByRole("button", { name: /select a time span/i }),
		);
		await user.click(
			await screen.findByRole("button", { name: /Relative time/i }),
		);
		const input = screen.getByPlaceholderText(
			/Relative time \(15m, 1h, 1d, 1w\)/i,
		);
		await user.clear(input);
		await user.type(input, "2h");
		// Choose "Next 2 hours"
		await user.click(
			await screen.findByRole("button", { name: /Next 2 hours/i }),
		);
		expect(onChange).toHaveBeenCalled();
		// Trigger text should reflect selection
		expect(
			screen.getByRole("button", { name: /Next 2 hours/i }),
		).toBeInTheDocument();
	});

	it("range mode allows manual date/time entry and apply", async () => {
		let applied: DateRangeSelectValue = null;
		const onChange = vi.fn((v: DateRangeSelectValue) => {
			applied = v;
		});
		render(<Controlled onExternalChange={onChange} />);
		await user.click(
			screen.getByRole("button", { name: /select a time span/i }),
		);
		await user.click(
			await screen.findByRole("button", { name: /Date range/i }),
		);

		const dateInputs = Array.from(
			document.querySelectorAll<HTMLInputElement>('input[type="date"]'),
		);
		const timeInputs = Array.from(
			document.querySelectorAll<HTMLInputElement>('input[type="time"]'),
		);
		const [fromDate, toDate] = dateInputs;
		const [fromTime, toTime] = timeInputs;

		await user.clear(fromDate);
		await user.type(fromDate, "2025-01-01");
		await user.clear(fromTime);
		await user.type(fromTime, "10:30");

		await user.clear(toDate);
		await user.type(toDate, "2025-01-02");
		await user.clear(toTime);
		await user.type(toTime, "12:00");

		await user.click(screen.getByRole("button", { name: /^Apply$/ }));
		expect(onChange).toHaveBeenCalled();
		const value = applied;
		if (!isRange(value)) throw new Error("Expected range value");
		// Applied; popover closed and placeholder removed
		expect(screen.queryByText("Select a time span")).not.toBeInTheDocument();
	});

	it("Now buttons set the respective endpoint to the current minute", async () => {
		let value: DateRangeSelectValue = null;
		const onChange = vi.fn((v: DateRangeSelectValue) => {
			value = v;
		});
		render(<RichDateRangeSelector value={value} onValueChange={onChange} />);
		await user.click(
			screen.getByRole("button", { name: /select a time span/i }),
		);
		await user.click(
			await screen.findByRole("button", { name: /Date range/i }),
		);

		// Click the two Now buttons
		const nowButtons = screen.getAllByRole("button", { name: /^Now$/ });
		await user.click(nowButtons[0]);
		await user.click(nowButtons[1]);

		const timeInputs = Array.from(
			document.querySelectorAll<HTMLInputElement>('input[type="time"]'),
		);
		const expected = new Date();
		const expectedTime = `${String(expected.getHours()).padStart(2, "0")}:${String(
			expected.getMinutes(),
		).padStart(2, "0")}`;
		expect(timeInputs[0].value).toBe(expectedTime);
		expect(timeInputs[1].value).toBe(expectedTime);
	});

	it("clear button clears value when clearable", async () => {
		let value: DateRangeSelectValue = { type: "period", period: "Today" };
		const onChange = vi.fn((v: DateRangeSelectValue) => {
			value = v;
		});
		render(
			<RichDateRangeSelector
				value={value}
				onValueChange={onChange}
				clearable
			/>,
		);
		const clearBtn = screen.getByRole("button", { name: /clear date range/i });
		await user.click(clearBtn);
		expect(onChange).toHaveBeenCalledWith(null);
	});

	it("previous/next buttons enable/disable appropriately with min/max", async () => {
		// Start with Past day selection
		let value: DateRangeSelectValue = { type: "span", seconds: -86400 };
		const min = new Date("2025-01-14T00:00:00"); // Going previous would be before this
		const max = new Date("2025-01-20T23:59:59");
		const onChange = vi.fn((v: DateRangeSelectValue) => {
			value = v;
		});
		render(
			<RichDateRangeSelector
				value={value}
				onValueChange={onChange}
				min={min}
				max={max}
			/>,
		);
		const prev = screen.getByRole("button", { name: /previous range/i });
		const next = screen.getByRole("button", { name: /next range/i });

		// With min near, going previous should be disabled; next enabled
		expect(prev).toBeDisabled();
		expect(next).not.toBeDisabled();

		// Clicking next should produce a range value (span transforms to range for stepping)
		await user.click(next);
		expect(onChange).toHaveBeenCalled();
		if (value && typeof value === "object" && "type" in value) {
			expect(value.type).toBe("range");
		} else {
			throw new Error("Expected range value");
		}
	});
});
