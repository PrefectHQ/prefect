import { render, screen } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import { createFakeSimpleFlowRuns } from "@/mocks";
import {
	createXAxisTickFormatter,
	FlowRunsScatterPlot,
	formatYAxisTick,
	generateNiceTimeTicks,
} from "./flow-runs-scatter-plot";

describe("FlowRunsScatterPlot", () => {
	it("renders the scatter plot when history data is provided", () => {
		const history = createFakeSimpleFlowRuns(10);

		render(<FlowRunsScatterPlot history={history} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByTestId("scatter-plot")).toBeInTheDocument();
	});

	it("returns null when history is empty", () => {
		const { container } = render(<FlowRunsScatterPlot history={[]} />, {
			wrapper: createWrapper(),
		});

		expect(container.firstChild).toBeNull();
	});

	it("renders with custom start and end dates", () => {
		const history = createFakeSimpleFlowRuns(5);
		const startDate = new Date("2024-01-01");
		const endDate = new Date("2024-01-31");

		render(
			<FlowRunsScatterPlot
				history={history}
				startDate={startDate}
				endDate={endDate}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByTestId("scatter-plot")).toBeInTheDocument();
	});

	it("is hidden on small screens via CSS class", () => {
		const history = createFakeSimpleFlowRuns(3);

		render(<FlowRunsScatterPlot history={history} />, {
			wrapper: createWrapper(),
		});

		const scatterPlot = screen.getByTestId("scatter-plot");
		expect(scatterPlot).toHaveClass("hidden", "md:block");
	});
});

describe("formatYAxisTick", () => {
	it("returns '0s' for zero", () => {
		expect(formatYAxisTick(0)).toBe("0s");
	});

	it("formats sub-second values with decimal", () => {
		expect(formatYAxisTick(0.5)).toBe("0.50s");
		expect(formatYAxisTick(0.123)).toBe("0.12s");
	});

	it("formats seconds", () => {
		expect(formatYAxisTick(1)).toBe("1s");
		expect(formatYAxisTick(30)).toBe("30s");
		expect(formatYAxisTick(59)).toBe("59s");
	});

	it("formats minutes", () => {
		expect(formatYAxisTick(60)).toBe("1m");
		expect(formatYAxisTick(120)).toBe("2m");
		expect(formatYAxisTick(3599)).toBe("59m");
	});

	it("formats hours", () => {
		expect(formatYAxisTick(3600)).toBe("1h");
		expect(formatYAxisTick(7200)).toBe("2h");
		expect(formatYAxisTick(86399)).toBe("23h");
	});

	it("formats days", () => {
		expect(formatYAxisTick(86400)).toBe("1d");
		expect(formatYAxisTick(172800)).toBe("2d");
		expect(formatYAxisTick(604800)).toBe("7d");
	});

	it("formats years", () => {
		expect(formatYAxisTick(31536000)).toBe("1y");
		expect(formatYAxisTick(63072000)).toBe("2y");
	});
});

describe("generateNiceTimeTicks", () => {
	it("returns single tick for zero or negative range", () => {
		const start = Date.now();
		expect(generateNiceTimeTicks(start, start, 5)).toEqual([start]);
		expect(generateNiceTimeTicks(start, start - 1000, 5)).toEqual([start]);
	});

	it("generates ticks aligned to second boundaries for short ranges", () => {
		const start = new Date("2024-01-15T12:00:00.000Z").getTime();
		const end = new Date("2024-01-15T12:00:10.000Z").getTime();
		const ticks = generateNiceTimeTicks(start, end, 5);

		expect(ticks.length).toBeGreaterThan(0);
		ticks.forEach((tick) => {
			expect(tick % 1000).toBe(0);
		});
	});

	it("generates ticks aligned to minute boundaries for minute ranges", () => {
		const start = new Date("2024-01-15T12:00:00.000Z").getTime();
		const end = new Date("2024-01-15T12:30:00.000Z").getTime();
		const ticks = generateNiceTimeTicks(start, end, 5);

		expect(ticks.length).toBeGreaterThan(0);
		ticks.forEach((tick) => {
			expect(tick % (60 * 1000)).toBe(0);
		});
	});

	it("generates ticks aligned to hour boundaries for hour ranges", () => {
		const start = new Date("2024-01-15T00:00:00.000Z").getTime();
		const end = new Date("2024-01-15T12:00:00.000Z").getTime();
		const ticks = generateNiceTimeTicks(start, end, 5);

		expect(ticks.length).toBeGreaterThan(0);
		ticks.forEach((tick) => {
			expect(tick % (60 * 60 * 1000)).toBe(0);
		});
	});

	it("generates ticks aligned to day boundaries for multi-day ranges", () => {
		const start = new Date("2024-01-01T00:00:00.000Z").getTime();
		const end = new Date("2024-01-08T00:00:00.000Z").getTime();
		const ticks = generateNiceTimeTicks(start, end, 5);

		expect(ticks.length).toBeGreaterThan(0);
		ticks.forEach((tick) => {
			expect(tick % (24 * 60 * 60 * 1000)).toBe(0);
		});
	});

	it("returns at least one tick even for very small ranges", () => {
		const start = Date.now();
		const end = start + 100;
		const ticks = generateNiceTimeTicks(start, end, 5);

		expect(ticks.length).toBeGreaterThanOrEqual(1);
	});
});

describe("createXAxisTickFormatter", () => {
	const formatter = createXAxisTickFormatter();

	it("formats milliseconds when crossing millisecond boundary", () => {
		const date = new Date("2024-01-15T12:30:45.123Z");
		const result = formatter(date.getTime());
		expect(result).toBe(".123");
	});

	it("formats seconds when crossing second boundary", () => {
		const date = new Date("2024-01-15T12:30:45.000Z");
		const result = formatter(date.getTime());
		expect(result).toBe(":45");
	});

	it("formats hour:minute when crossing minute boundary", () => {
		const date = new Date("2024-01-15T12:30:00.000Z");
		const result = formatter(date.getTime());
		expect(result).toMatch(/12:30|30/);
	});

	it("formats hour when crossing hour boundary", () => {
		const date = new Date("2024-01-15T12:00:00.000Z");
		const result = formatter(date.getTime());
		expect(result).toMatch(/12|PM|AM|noon/i);
	});

	it("formats weekday and day when crossing day boundary", () => {
		const date = new Date("2024-01-15T00:00:00.000Z");
		const result = formatter(date.getTime());
		expect(result).toMatch(/Mon|15|Jan/i);
	});

	it("formats month when crossing month boundary", () => {
		const date = new Date("2024-06-01T00:00:00.000Z");
		const result = formatter(date.getTime());
		expect(result).toMatch(/June|Jun|Sat|1/i);
	});

	it("formats year when crossing year boundary", () => {
		const date = new Date("2024-01-01T00:00:00.000Z");
		const result = formatter(date.getTime());
		expect(result).toMatch(/2024|January|Jan|Mon|1/i);
	});
});
