import { fireEvent, render } from "@testing-library/react";
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
		startDate: twentyFourHoursAgo,
		endDate: now,
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

	it("sets crosshair cursor for drag-to-select interaction", () => {
		const { container } = render(<InteractiveEventsChart {...defaultProps} />);
		const wrapper = container.firstChild as HTMLElement;
		expect(wrapper.style.cursor).toBe("crosshair");
	});

	it("shows selection overlay during drag", () => {
		const { container } = render(<InteractiveEventsChart {...defaultProps} />);
		const wrapper = container.firstChild as HTMLElement;

		// Mock getBoundingClientRect for the container
		vi.spyOn(wrapper, "getBoundingClientRect").mockReturnValue({
			left: 0,
			right: 1000,
			width: 1000,
			top: 0,
			bottom: 200,
			height: 200,
			x: 0,
			y: 0,
			toJSON: () => ({}),
		});

		// Start drag at 25% of the chart (6 hours in)
		fireEvent.mouseDown(wrapper, { clientX: 250, button: 0 });

		// Drag to 75% of the chart (18 hours in)
		fireEvent.mouseMove(wrapper, { clientX: 750 });

		// Selection overlay should be visible
		const overlay = wrapper.querySelector(".bg-primary\\/20");
		expect(overlay).toBeInTheDocument();
	});

	it("calls onSelectionChange when drag completes with sufficient range", () => {
		const onSelectionChange = vi.fn();
		const { container } = render(
			<InteractiveEventsChart
				{...defaultProps}
				onSelectionChange={onSelectionChange}
			/>,
		);
		const wrapper = container.firstChild as HTMLElement;

		vi.spyOn(wrapper, "getBoundingClientRect").mockReturnValue({
			left: 0,
			right: 1000,
			width: 1000,
			top: 0,
			bottom: 200,
			height: 200,
			x: 0,
			y: 0,
			toJSON: () => ({}),
		});

		// Drag from 25% to 75%
		fireEvent.mouseDown(wrapper, { clientX: 250, button: 0 });
		fireEvent.mouseMove(wrapper, { clientX: 750 });
		fireEvent.mouseUp(wrapper);

		expect(onSelectionChange).toHaveBeenCalledWith(
			expect.any(Date),
			expect.any(Date),
		);

		const [start, end] = onSelectionChange.mock.calls[0] as [Date, Date];
		expect(start.getTime()).toBeLessThan(end.getTime());
	});

	it("does not call onSelectionChange for sub-second selections", () => {
		const onSelectionChange = vi.fn();
		const { container } = render(
			<InteractiveEventsChart
				{...defaultProps}
				onSelectionChange={onSelectionChange}
			/>,
		);
		const wrapper = container.firstChild as HTMLElement;

		vi.spyOn(wrapper, "getBoundingClientRect").mockReturnValue({
			left: 0,
			right: 1000,
			width: 1000,
			top: 0,
			bottom: 200,
			height: 200,
			x: 0,
			y: 0,
			toJSON: () => ({}),
		});

		// Click without meaningful drag (same position)
		fireEvent.mouseDown(wrapper, { clientX: 500, button: 0 });
		fireEvent.mouseUp(wrapper);

		expect(onSelectionChange).not.toHaveBeenCalled();
	});
});
