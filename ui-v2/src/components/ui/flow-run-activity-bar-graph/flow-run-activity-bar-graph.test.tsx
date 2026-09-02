import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	FlowRunActivityBarChart,
	FlowRunActivityBarGraphTooltipProvider,
} from "./index";

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
	])(
		"renders the bars with expected colors for %s",
		(stateType, expectedClass) => {
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
			expect(
				within(bars[0]).getByTestId("bar-rect-test-flow-run-1"),
			).toHaveClass(expectedClass);
		},
	);

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

	describe("tooltip", () => {
		const hourlyFlowRuns = Array.from({ length: 4 }, (_, i) => ({
			...mockFlowRun,
			id: `run-${i}`,
			name: `run-${i}`,
			start_time: new Date(Date.UTC(2024, 0, 1, i)).toISOString(),
		}));
		const tooltipProps = {
			enrichedFlowRuns: hourlyFlowRuns,
			startDate: new Date("2024-01-01T00:00:00Z"),
			endDate: new Date("2024-01-01T04:00:00Z"),
			numberOfBars: 4,
		};

		const renderWithRouter = async (component: ReactNode) => {
			// The router resolves asynchronously, so render with real timers and
			// switch to fake ones once the chart is on screen.
			vi.useRealTimers();
			const router = createRouter({
				routeTree: createRootRoute({ component: () => component }),
				history: createMemoryHistory({ initialEntries: ["/"] }),
			});
			const view = render(<RouterProvider router={router} />);
			await screen.findAllByTestId("bar-rect-run-0");
			vi.useFakeTimers();
			return view;
		};

		// Recharts resolves pointer positions on the next animation frame
		const hoverBar = (chart: Element, bar: Element) => {
			const x = Number(bar.getAttribute("x"));
			const width = Number(bar.getAttribute("width"));
			fireEvent.mouseMove(chart, { clientX: x + width / 2, clientY: 100 });
			act(() => {
				vi.advanceTimersByTime(20);
			});
		};

		const getSvg = (container: HTMLElement) => {
			const svg = container.querySelector("svg.recharts-surface");
			if (!(svg instanceof SVGSVGElement)) throw new Error("no chart svg");
			return svg;
		};

		const getTooltipRunLink = (name: string) =>
			screen.queryByRole("link", { name });

		it("keeps showing the first hovered run while the cursor crosses a neighbor", async () => {
			const { container } = await renderWithRouter(
				/* @ts-expect-error - Type error from test data not matching schema */
				<FlowRunActivityBarChart {...tooltipProps} />,
			);
			const svg = getSvg(container);

			hoverBar(svg, screen.getByTestId("bar-rect-run-0"));
			expect(getTooltipRunLink("run-0")).toBeVisible();

			hoverBar(svg, screen.getByTestId("bar-rect-run-1"));
			expect(getTooltipRunLink("run-0")).toBeVisible();
			expect(getTooltipRunLink("run-1")).not.toBeInTheDocument();

			act(() => {
				vi.advanceTimersByTime(150);
			});
			expect(getTooltipRunLink("run-0")).not.toBeInTheDocument();
			expect(getTooltipRunLink("run-1")).toBeVisible();
		});

		it("freezes the tooltip while the cursor is inside it", async () => {
			const { container } = await renderWithRouter(
				/* @ts-expect-error - Type error from test data not matching schema */
				<FlowRunActivityBarChart {...tooltipProps} />,
			);
			const svg = getSvg(container);

			hoverBar(svg, screen.getByTestId("bar-rect-run-0"));
			const link = getTooltipRunLink("run-0");
			if (!link) throw new Error("tooltip did not open");
			const card = link.closest('[data-slot="card"]');
			if (!card) throw new Error("tooltip card not found");

			hoverBar(svg, screen.getByTestId("bar-rect-run-1"));
			// React derives enter/leave from `mouseout` on the element being left
			fireEvent.mouseOut(svg, { relatedTarget: card });
			act(() => {
				vi.advanceTimersByTime(1000);
			});

			expect(getTooltipRunLink("run-0")).toHaveAttribute(
				"href",
				"/runs/flow-run/run-0",
			);
			expect(getTooltipRunLink("run-1")).not.toBeInTheDocument();

			fireEvent.mouseOut(card, { relatedTarget: svg });
			act(() => {
				vi.advanceTimersByTime(150);
			});
			expect(getTooltipRunLink("run-1")).toBeVisible();
		});

		it("never shows two tooltips when the cursor moves to another chart", async () => {
			const { container } = await renderWithRouter(
				<FlowRunActivityBarGraphTooltipProvider>
					<div data-testid="chart-a">
						{/* @ts-expect-error - Type error from test data not matching schema */}
						<FlowRunActivityBarChart chartId="a" {...tooltipProps} />
					</div>
					<div data-testid="chart-b">
						{/* @ts-expect-error - Type error from test data not matching schema */}
						<FlowRunActivityBarChart chartId="b" {...tooltipProps} />
					</div>
				</FlowRunActivityBarGraphTooltipProvider>,
			);
			const chartA = within(screen.getByTestId("chart-a"));
			const chartB = within(screen.getByTestId("chart-b"));
			const svgA = getSvg(screen.getByTestId("chart-a"));
			const svgB = getSvg(screen.getByTestId("chart-b"));
			const countCards = () =>
				container.querySelectorAll('[data-slot="card"]').length;

			hoverBar(svgA, chartA.getByTestId("bar-rect-run-0"));
			expect(chartA.getByRole("link", { name: "run-0" })).toBeVisible();

			fireEvent.mouseOut(svgA, { relatedTarget: svgB });
			hoverBar(svgB, chartB.getByTestId("bar-rect-run-1"));

			// Step through the leave and switch delays of both charts
			for (let elapsed = 0; elapsed < 600; elapsed += 50) {
				expect(countCards()).toBeLessThanOrEqual(1);
				act(() => {
					vi.advanceTimersByTime(50);
				});
			}

			expect(chartA.queryByRole("link", { name: "run-0" })).toBeNull();
			expect(chartB.getByRole("link", { name: "run-1" })).toBeVisible();
			expect(countCards()).toBe(1);
		});
	});
});
