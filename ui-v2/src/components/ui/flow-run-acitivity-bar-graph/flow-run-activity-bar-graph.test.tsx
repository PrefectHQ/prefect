import { router } from "@/router";
import { RouterContextProvider } from "@tanstack/react-router";
import { fireEvent, render, screen, within } from "@testing-library/react";
import {
	afterEach,
	beforeAll,
	beforeEach,
	describe,
	expect,
	it,
	vi,
} from "vitest";
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

beforeAll(() => {
	class ResizeObserverMock {
		observe() {}
		unobserve() {}
		disconnect() {}
	}

	global.ResizeObserver = ResizeObserverMock;
});

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

	it("shows tooltip on bar hover", () => {
		render(
			<RouterContextProvider router={router}>
				{/* @ts-expect-error - Type error from test data not matching schema */}
				<FlowRunActivityBarChart {...defaultProps} numberOfBars={1} />
			</RouterContextProvider>,
		);

		const bar = screen.getByTestId("bar-rect-test-flow-run-1");
		fireEvent.mouseOver(bar);

		// Check if tooltip content appears
		expect(screen.getByText("Test Flow")).toBeInTheDocument();
		expect(screen.getByText("Test Flow Run")).toBeInTheDocument();
		expect(screen.getByText("Test Deployment")).toBeInTheDocument();
		// Check if state badge is rendered
		expect(screen.getByText("Completed")).toBeInTheDocument();
		// Check if tags are rendered
		expect(screen.getByText("test-tag")).toBeInTheDocument();
	});

	it("renders correct number of bars", () => {
		const { rerender } = render(
			<RouterContextProvider router={router}>
				{/* @ts-expect-error - Type error from test data not matching schema */}
				<FlowRunActivityBarChart {...defaultProps} />
			</RouterContextProvider>,
		);

		let bars = screen.getAllByRole("graphics-symbol");
		expect(bars).toHaveLength(defaultProps.numberOfBars);

		rerender(
			<RouterContextProvider router={router}>
				{/* @ts-expect-error - Type error from test data not matching schema */}
				<FlowRunActivityBarChart {...defaultProps} numberOfBars={10} />
			</RouterContextProvider>,
		);

		bars = screen.getAllByRole("graphics-symbol");
		expect(bars).toHaveLength(10);
	});

	it.each([
		["COMPLETED", "fill-green-600"],
		["FAILED", "fill-red-600"],
		["CANCELLED", "fill-gray-500"],
		["CANCELLING", "fill-gray-600"],
		["PENDING", "fill-gray-400"],
		["SCHEDULED", "fill-yellow-400"],
		["PAUSED", "fill-gray-500"],
		["RUNNING", "fill-blue-700"],
		["CRASHED", "fill-orange-600"],
	])(
		"renders the bars with expected colors for %s",
		(stateType, expectedClass) => {
			const enrichedFlowRun = {
				...mockFlowRun,
				state_type: stateType,
			};
			render(
				<RouterContextProvider router={router}>
					<FlowRunActivityBarChart
						{...defaultProps}
						// @ts-expect-error - Type error from test data not matching schema
						enrichedFlowRuns={[enrichedFlowRun]}
					/>
				</RouterContextProvider>,
			);
			const bars = screen.getAllByRole("graphics-symbol");
			expect(
				within(bars[0]).getByTestId("bar-rect-test-flow-run-1"),
			).toHaveClass(expectedClass);
		},
	);

	it("applies custom bar width when provided", () => {
		const customBarWidth = 12;
		render(
			<RouterContextProvider router={router}>
				{/* @ts-expect-error - Type error from test data not matching schema */}
				<FlowRunActivityBarChart {...defaultProps} barWidth={customBarWidth} />
			</RouterContextProvider>,
		);

		const bar = screen.getByTestId("bar-rect-test-flow-run-1");
		expect(bar).toHaveAttribute("width", customBarWidth.toString());
	});
});
