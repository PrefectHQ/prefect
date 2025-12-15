import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { EventsCount } from "@/api/events";
import { InteractiveEventsChart } from "./interactive-events-chart";

const createMockEventsCount = (
	startTime: Date,
	count: number,
	label?: string,
): EventsCount => ({
	value: startTime.toISOString(),
	start_time: startTime.toISOString(),
	end_time: new Date(startTime.getTime() + 3600000).toISOString(),
	count,
	label: label ?? `${count} events`,
});

const generateMockData = (startDate: Date, hours: number): EventsCount[] => {
	return Array.from({ length: hours }, (_, i) => {
		const time = new Date(startDate.getTime() + i * 3600000);
		const count = Math.floor(Math.random() * 100 + 10);
		return createMockEventsCount(time, count);
	});
};

describe("InteractiveEventsChart", () => {
	const now = new Date();
	const twentyFourHoursAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);

	const defaultProps = {
		data: generateMockData(twentyFourHoursAgo, 24),
		zoomStart: twentyFourHoursAgo,
		zoomEnd: now,
		onZoomChange: vi.fn(),
	};

	it("renders without crashing", () => {
		const { container } = render(<InteractiveEventsChart {...defaultProps} />);
		expect(container.firstChild).toBeInTheDocument();
	});

	it("renders with empty data", () => {
		const { container } = render(
			<InteractiveEventsChart {...defaultProps} data={[]} />,
		);
		expect(container.firstChild).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const { container } = render(
			<InteractiveEventsChart {...defaultProps} className="custom-class" />,
		);
		expect(container.firstChild).toHaveClass("custom-class");
	});

	it("does not show clear selection button when no selection exists", () => {
		render(<InteractiveEventsChart {...defaultProps} />);
		expect(screen.queryByText("Clear selection")).not.toBeInTheDocument();
	});

	it("shows clear selection button when selection exists (controlled mode)", () => {
		const selectionStart = new Date(twentyFourHoursAgo.getTime() + 6 * 3600000);
		const selectionEnd = new Date(twentyFourHoursAgo.getTime() + 12 * 3600000);

		render(
			<InteractiveEventsChart
				{...defaultProps}
				selectionStart={selectionStart}
				selectionEnd={selectionEnd}
			/>,
		);

		expect(screen.getByText("Clear selection")).toBeInTheDocument();
	});

	it("calls onSelectionChange with null values when clear selection is clicked", async () => {
		const user = userEvent.setup();
		const onSelectionChange = vi.fn();
		const selectionStart = new Date(twentyFourHoursAgo.getTime() + 6 * 3600000);
		const selectionEnd = new Date(twentyFourHoursAgo.getTime() + 12 * 3600000);

		render(
			<InteractiveEventsChart
				{...defaultProps}
				selectionStart={selectionStart}
				selectionEnd={selectionEnd}
				onSelectionChange={onSelectionChange}
			/>,
		);

		const clearButton = screen.getByText("Clear selection");
		await user.click(clearButton);

		expect(onSelectionChange).toHaveBeenCalledWith(null, null);
	});

	it("renders selection area when selectionStart and selectionEnd are provided", () => {
		const selectionStart = new Date(twentyFourHoursAgo.getTime() + 6 * 3600000);
		const selectionEnd = new Date(twentyFourHoursAgo.getTime() + 12 * 3600000);

		render(
			<InteractiveEventsChart
				{...defaultProps}
				selectionStart={selectionStart}
				selectionEnd={selectionEnd}
			/>,
		);

		expect(screen.getByText("Clear selection")).toBeInTheDocument();
	});

	it("does not show clear selection button when only selectionStart is provided", () => {
		const selectionStart = new Date(twentyFourHoursAgo.getTime() + 6 * 3600000);

		render(
			<InteractiveEventsChart
				{...defaultProps}
				selectionStart={selectionStart}
			/>,
		);

		expect(screen.queryByText("Clear selection")).not.toBeInTheDocument();
	});

	it("does not show clear selection button when only selectionEnd is provided", () => {
		const selectionEnd = new Date(twentyFourHoursAgo.getTime() + 12 * 3600000);

		render(
			<InteractiveEventsChart {...defaultProps} selectionEnd={selectionEnd} />,
		);

		expect(screen.queryByText("Clear selection")).not.toBeInTheDocument();
	});

	it("passes onZoomChange to zoom hook", () => {
		const onZoomChange = vi.fn();

		const { container } = render(
			<InteractiveEventsChart {...defaultProps} onZoomChange={onZoomChange} />,
		);

		expect(container.firstChild).toBeInTheDocument();
	});

	it("passes onSelectionChange to selection hook", () => {
		const onSelectionChange = vi.fn();

		const { container } = render(
			<InteractiveEventsChart
				{...defaultProps}
				onSelectionChange={onSelectionChange}
			/>,
		);

		expect(container.firstChild).toBeInTheDocument();
	});

	it("applies select-none class to prevent text selection during drag", () => {
		const { container } = render(<InteractiveEventsChart {...defaultProps} />);
		expect(container.firstChild).toHaveClass("select-none");
	});

	it("renders with controlled selection values", () => {
		const selectionStart = new Date(twentyFourHoursAgo.getTime() + 6 * 3600000);
		const selectionEnd = new Date(twentyFourHoursAgo.getTime() + 12 * 3600000);

		const { rerender } = render(
			<InteractiveEventsChart
				{...defaultProps}
				selectionStart={selectionStart}
				selectionEnd={selectionEnd}
			/>,
		);

		expect(screen.getByText("Clear selection")).toBeInTheDocument();

		// Update controlled values to null
		rerender(
			<InteractiveEventsChart
				{...defaultProps}
				selectionStart={null}
				selectionEnd={null}
			/>,
		);

		expect(screen.queryByText("Clear selection")).not.toBeInTheDocument();
	});
});
