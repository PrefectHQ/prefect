import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { DateRangeSelect, type DateRangeValue } from "./date-range-select";

describe("DateRangeSelect", () => {
	const mockOnChange = vi.fn();

	beforeEach(() => {
		mockOnChange.mockClear();
	});

	it("renders with placeholder text when no value is provided", () => {
		render(
			<DateRangeSelect
				value={null}
				onChange={mockOnChange}
				placeholder="Select date range"
			/>,
		);

		expect(screen.getByText("Select date range")).toBeInTheDocument();
	});

	it("displays the correct label for span values", () => {
		const spanValue: DateRangeValue = { type: "span", seconds: -604800 };
		render(<DateRangeSelect value={spanValue} onChange={mockOnChange} />);

		expect(screen.getByText("Last 7 days")).toBeInTheDocument();
	});

	it("displays the correct label for range values", () => {
		const rangeValue: DateRangeValue = {
			type: "range",
			startDate: new Date("2024-01-01"),
			endDate: new Date("2024-01-07"),
		};
		render(<DateRangeSelect value={rangeValue} onChange={mockOnChange} />);

		expect(screen.getByText("Jan 01 - Jan 07")).toBeInTheDocument();
	});

	it("opens popover when clicked", async () => {
		const user = userEvent.setup();
		render(
			<DateRangeSelect
				value={null}
				onChange={mockOnChange}
				placeholder="Select date range"
			/>,
		);

		const button = screen.getByRole("button", { name: /select date range/i });
		await user.click(button);

		expect(screen.getByText("Quick ranges")).toBeInTheDocument();
		expect(screen.getByText("Custom range")).toBeInTheDocument();
	});

	it("calls onChange when a preset range is selected", async () => {
		const user = userEvent.setup();
		render(
			<DateRangeSelect
				value={null}
				onChange={mockOnChange}
				placeholder="Select date range"
			/>,
		);

		const button = screen.getByRole("button", { name: /select date range/i });
		await user.click(button);

		const lastSevenDaysButton = screen.getByRole("button", {
			name: "Last 7 days",
		});
		await user.click(lastSevenDaysButton);

		expect(mockOnChange).toHaveBeenCalledWith({
			type: "span",
			seconds: -604800,
		});
	});

	it("displays custom range labels correctly", () => {
		const customSpanValue: DateRangeValue = { type: "span", seconds: -172800 }; // 2 days
		render(<DateRangeSelect value={customSpanValue} onChange={mockOnChange} />);

		expect(screen.getByText("Last 2 days")).toBeInTheDocument();
	});

	it("handles single day span correctly", () => {
		const singleDayValue: DateRangeValue = { type: "span", seconds: -86400 }; // 1 day
		render(<DateRangeSelect value={singleDayValue} onChange={mockOnChange} />);

		expect(screen.getByText("Last 1 day")).toBeInTheDocument();
	});
});
