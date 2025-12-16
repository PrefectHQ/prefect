import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { EventsCount } from "@/api/events";
import { EventsLineChart } from "./events-line-chart";

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

describe("EventsLineChart", () => {
	const now = new Date();
	const twentyFourHoursAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);

	const defaultProps = {
		data: generateMockData(twentyFourHoursAgo, 24),
	};

	it("renders without crashing", () => {
		render(<EventsLineChart {...defaultProps} />);
		expect(screen.getByRole("application")).toBeInTheDocument();
	});

	it("renders with empty data", () => {
		render(<EventsLineChart data={[]} />);
		expect(screen.getByRole("application")).toBeInTheDocument();
	});

	it("renders with single data point", () => {
		const singleDataPoint = [createMockEventsCount(now, 42)];
		render(<EventsLineChart data={singleDataPoint} />);
		expect(screen.getByRole("application")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const { container } = render(
			<EventsLineChart {...defaultProps} className="custom-class" />,
		);
		expect(container.firstChild).toHaveClass("custom-class");
	});

	it("calls onCursorChange with null on mouse leave", () => {
		const onCursorChange = vi.fn();
		render(
			<EventsLineChart {...defaultProps} onCursorChange={onCursorChange} />,
		);

		expect(screen.getByRole("application")).toBeInTheDocument();
	});

	it("exposes clearSelection method via ref", () => {
		const ref = { current: null } as React.RefObject<{
			clearSelection: () => void;
		} | null>;

		render(<EventsLineChart {...defaultProps} ref={ref} />);

		expect(ref.current).not.toBeNull();
		expect(typeof ref.current?.clearSelection).toBe("function");
	});
});
