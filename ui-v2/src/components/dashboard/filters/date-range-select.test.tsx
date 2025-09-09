import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { DateRangeSelect } from "./date-range-select";
import type { DateRangeSelectValue } from "./types";

describe("DateRangeSelect", () => {
	test("renders with placeholder when no value", () => {
		const onValueChange = vi.fn();
		render(
			<DateRangeSelect
				onValueChange={onValueChange}
				placeholder="Select range"
			/>,
		);

		expect(screen.getByText("Select range")).toBeInTheDocument();
	});

	test("renders with value label when value provided", () => {
		const value: DateRangeSelectValue = { type: "span", seconds: -86400 };
		const onValueChange = vi.fn();

		render(<DateRangeSelect value={value} onValueChange={onValueChange} />);

		expect(screen.getByText("1 day")).toBeInTheDocument();
	});

	test("opens popover when trigger button is clicked", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();

		render(<DateRangeSelect onValueChange={onValueChange} />);

		const trigger = screen.getByRole("button");
		await user.click(trigger);

		await waitFor(() => {
			expect(screen.getByText("Last hour")).toBeInTheDocument();
			expect(screen.getByText("Last day")).toBeInTheDocument();
			expect(screen.getByText("Last 7 days")).toBeInTheDocument();
			expect(screen.getByText("Last 30 days")).toBeInTheDocument();
			expect(screen.getByText("Last 90 days")).toBeInTheDocument();
		});
	});

	test("calls onValueChange when preset is selected", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();

		render(<DateRangeSelect onValueChange={onValueChange} />);

		const trigger = screen.getByRole("button");
		await user.click(trigger);

		await waitFor(() => {
			expect(screen.getByText("Last day")).toBeInTheDocument();
		});

		const lastDayOption = screen.getByText("Last day");
		await user.click(lastDayOption);

		expect(onValueChange).toHaveBeenCalledWith({
			type: "span",
			seconds: -86400,
		});
	});

	test("shows custom range option", async () => {
		const user = userEvent.setup();
		const onValueChange = vi.fn();

		render(<DateRangeSelect onValueChange={onValueChange} />);

		const trigger = screen.getByRole("button");
		await user.click(trigger);

		await waitFor(() => {
			expect(screen.getByText("Custom range")).toBeInTheDocument();
		});
	});

	test("shows navigation buttons for span values", () => {
		const value: DateRangeSelectValue = { type: "span", seconds: -86400 };
		const onValueChange = vi.fn();

		render(<DateRangeSelect value={value} onValueChange={onValueChange} />);

		const buttons = screen.getAllByRole("button");
		expect(buttons).toHaveLength(4); // Previous, main trigger, clear, next
	});

	test("shows clear button when clearable and has value", () => {
		const value: DateRangeSelectValue = { type: "span", seconds: -86400 };
		const onValueChange = vi.fn();

		render(
			<DateRangeSelect
				value={value}
				onValueChange={onValueChange}
				clearable={true}
			/>,
		);

		const clearButtons = screen
			.getAllByRole("button")
			.filter((button) =>
				button.querySelector("svg")?.classList.contains("lucide-x"),
			);
		expect(clearButtons).toHaveLength(1);
	});

	test("calls onValueChange with null when cleared", async () => {
		const user = userEvent.setup();
		const value: DateRangeSelectValue = { type: "span", seconds: -86400 };
		const onValueChange = vi.fn();

		render(
			<DateRangeSelect
				value={value}
				onValueChange={onValueChange}
				clearable={true}
			/>,
		);

		const clearButtons = screen
			.getAllByRole("button")
			.filter((button) =>
				button.querySelector("svg")?.classList.contains("lucide-x"),
			);
		await user.click(clearButtons[0]);

		expect(onValueChange).toHaveBeenCalledWith(null);
	});

	test("does not show clear button when clearable is false", () => {
		const value: DateRangeSelectValue = { type: "span", seconds: -86400 };
		const onValueChange = vi.fn();

		render(
			<DateRangeSelect
				value={value}
				onValueChange={onValueChange}
				clearable={false}
			/>,
		);

		const clearButtons = screen
			.getAllByRole("button")
			.filter((button) =>
				button.querySelector("svg")?.classList.contains("lucide-x"),
			);
		expect(clearButtons).toHaveLength(0);
	});

	test("disables all buttons when disabled prop is true", () => {
		const value: DateRangeSelectValue = { type: "span", seconds: -86400 };
		const onValueChange = vi.fn();

		render(
			<DateRangeSelect
				value={value}
				onValueChange={onValueChange}
				disabled={true}
			/>,
		);

		const buttons = screen.getAllByRole("button");
		buttons.forEach((button) => {
			expect(button).toBeDisabled();
		});
	});

	test("handles range values correctly", () => {
		const value: DateRangeSelectValue = {
			type: "range",
			startDate: new Date("2024-01-01"),
			endDate: new Date("2024-01-31"),
		};
		const onValueChange = vi.fn();

		render(<DateRangeSelect value={value} onValueChange={onValueChange} />);

		expect(screen.getByText("Jan 1, 2024 - Jan 31, 2024")).toBeInTheDocument();
	});

	test("applies custom className", () => {
		const onValueChange = vi.fn();

		const { container } = render(
			<DateRangeSelect
				onValueChange={onValueChange}
				className="custom-class"
			/>,
		);

		expect(container.firstChild).toHaveClass("custom-class");
	});

	test("shows placeholder text with muted color when no value", () => {
		const onValueChange = vi.fn();

		render(
			<DateRangeSelect
				onValueChange={onValueChange}
				placeholder="Choose a date range"
			/>,
		);

		const button = screen.getByRole("button");
		expect(button).toHaveClass("text-muted-foreground");
		expect(screen.getByText("Choose a date range")).toBeInTheDocument();
	});
});
