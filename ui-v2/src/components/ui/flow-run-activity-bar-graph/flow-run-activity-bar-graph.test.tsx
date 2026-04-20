import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FlowRunActivityBarChart } from "./index";

const mockFlowRun = {
	id: "test-flow-run-1",
	name: "Test Flow Run",
	state_type: "COMPLETED",
	state: {
		type: "COMPLETED",
		name: "Completed",
	},
	start_time: "2024-01-01T00:00:00.000Z",
	total_run_time: 3600,
	tags: ["test-tag"],
	deployment: {
		id: "test-deployment-1",
		name: "Test Deployment",
	},
	flow: {
		id: "test-flow-1",
		name: "Test Flow",
	},
};

const mockEnrichedFlowRuns = [mockFlowRun];

describe("FlowRunActivityBarChart", () => {
	const defaultProps = {
		enrichedFlowRuns: mockEnrichedFlowRuns,
		startDate: new Date("2024-01-01"),
		endDate: new Date("2024-01-02"),
		numberOfBars: 24,
	};

	beforeEach(() => {
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("renders correct number of bars", () => {
		const { rerender } = render(
			/* @ts-expect-error - Type error from test data not matching schema */
			<FlowRunActivityBarChart {...defaultProps} />,
		);

		let bars = screen.getAllByRole("graphics-symbol");
		expect(bars).toHaveLength(defaultProps.numberOfBars);

		rerender(
			/* @ts-expect-error - Type error from test data not matching schema */
			<FlowRunActivityBarChart {...defaultProps} numberOfBars={10} />,
		);

		bars = screen.getAllByRole("graphics-symbol");
		expect(bars).toHaveLength(10);
	});

	it.each([
		["COMPLETED", "fill-state-completed-500"],
		["FAILED", "fill-state-failed-500"],
		["CANCELLED", "fill-state-cancelled-500"],
		["CANCELLING", "fill-state-cancelling-500"],
		["PENDING", "fill-state-pending-500"],
		["SCHEDULED", "fill-state-scheduled-500"],
		["PAUSED", "fill-state-paused-500"],
		["RUNNING", "fill-state-running-500"],
		["CRASHED", "fill-state-crashed-500"],
	])("renders the bars with expected colors for %s", (stateType, expectedClass) => {
		const enrichedFlowRun = {
			...mockFlowRun,
			state_type: stateType,
		};
		render(
			<FlowRunActivityBarChart
				{...defaultProps}
				// @ts-expect-error - Type error from test data not matching schema
				enrichedFlowRuns={[enrichedFlowRun]}
			/>,
		);
		const bars = screen.getAllByRole("graphics-symbol");
		expect(within(bars[0]).getByTestId("bar-rect-test-flow-run-1")).toHaveClass(
			expectedClass,
		);
	});

	it("applies custom bar width when provided", () => {
		const customBarWidth = 12;
		render(
			/* @ts-expect-error - Type error from test data not matching schema */
			<FlowRunActivityBarChart {...defaultProps} barWidth={customBarWidth} />,
		);

		const bar = screen.getByTestId("bar-rect-test-flow-run-1");
		expect(bar).toHaveAttribute("width", customBarWidth.toString());
	});

	it("renders without error when enrichedFlowRuns exceeds numberOfBars", () => {
		const manyFlowRuns = Array.from({ length: 50 }, (_, i) => ({
			...mockFlowRun,
			id: `test-flow-run-${i}`,
			start_time: new Date(
				new Date("2024-01-01").getTime() + i * 3600000,
			).toISOString(),
		}));

		// Should not throw when there are more flow runs than bars
		render(
			<FlowRunActivityBarChart
				{...defaultProps}
				// @ts-expect-error - Type error from test data not matching schema
				enrichedFlowRuns={manyFlowRuns}
				numberOfBars={10}
			/>,
		);

		// Should render exactly numberOfBars bars
		const bars = screen.getAllByRole("graphics-symbol");
		expect(bars).toHaveLength(10);
	});
});
