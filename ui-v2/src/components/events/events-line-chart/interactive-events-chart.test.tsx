import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
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
});
