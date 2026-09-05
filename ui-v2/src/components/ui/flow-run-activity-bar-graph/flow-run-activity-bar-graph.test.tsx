import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { type ReactNode, useState } from "react";
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
		const FlowRunDataHarness = ({
			withSecondChart = false,
		}: {
			withSecondChart?: boolean;
		}) => {
			const [flowRuns, setFlowRuns] = useState(hourlyFlowRuns);

			return (
				<>
					<button
						type="button"
						onClick={() => {
							setFlowRuns((current) =>
								current.map((flowRun) =>
									flowRun.id === "run-0"
										? { ...flowRun, name: "run-0 refreshed" }
										: flowRun,
								),
							);
						}}
					>
						Refresh data
					</button>
					<button
						type="button"
						onClick={() => {
							setFlowRuns((current) =>
								current.filter((flowRun) => flowRun.id !== "run-0"),
							);
						}}
					>
						Remove run 0
					</button>
					<FlowRunActivityBarGraphTooltipProvider>
						<div data-testid="refresh-chart-a">
							<FlowRunActivityBarChart
								chartId="refresh-a"
								{...tooltipProps}
								// @ts-expect-error - Type error from test data not matching schema
								enrichedFlowRuns={flowRuns}
							/>
						</div>
						{withSecondChart && (
							<div data-testid="refresh-chart-b">
								{/* @ts-expect-error - Type error from test data not matching schema */}
								<FlowRunActivityBarChart
									chartId="refresh-b"
									{...tooltipProps}
								/>
							</div>
						)}
					</FlowRunActivityBarGraphTooltipProvider>
				</>
			);
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

		it("refreshes hovered run details without moving the tooltip", async () => {
			const { container } = await renderWithRouter(<FlowRunDataHarness />);
			const svg = getSvg(container);

			hoverBar(svg, screen.getByTestId("bar-rect-run-0"));
			const link = getTooltipRunLink("run-0");
			if (!link) throw new Error("tooltip did not open");
			const card = link.closest('[data-slot="card"]');
			if (!(card instanceof HTMLElement)) {
				throw new Error("tooltip card not found");
			}
			hoverBar(svg, screen.getByTestId("bar-rect-run-1"));
			fireEvent.mouseOut(svg, { relatedTarget: card });
			act(() => {
				vi.advanceTimersByTime(1000);
			});
			expect(getTooltipRunLink("run-0")).toBeVisible();
			const initialPosition = { left: card.style.left, top: card.style.top };

			fireEvent.click(screen.getByRole("button", { name: "Refresh data" }));

			expect(getTooltipRunLink("run-0")).not.toBeInTheDocument();
			expect(getTooltipRunLink("run-0 refreshed")).toBeVisible();
			expect(card.style.left).toBe(initialPosition.left);
			expect(card.style.top).toBe(initialPosition.top);
		});

		it("dismisses a pinned tooltip when its run is removed", async () => {
			const { container } = await renderWithRouter(
				<FlowRunDataHarness withSecondChart />,
			);
			const chartA = screen.getByTestId("refresh-chart-a");
			const chartB = screen.getByTestId("refresh-chart-b");
			const svgA = getSvg(chartA);
			const svgB = getSvg(chartB);

			hoverBar(svgA, within(chartA).getByTestId("bar-rect-run-0"));
			const link = within(chartA).getByRole("link", { name: "run-0" });
			const card = link.closest('[data-slot="card"]');
			if (!card) throw new Error("tooltip card not found");
			hoverBar(svgA, within(chartA).getByTestId("bar-rect-run-1"));
			fireEvent.mouseOut(svgA, { relatedTarget: card });
			act(() => {
				vi.advanceTimersByTime(1000);
			});
			expect(link).toBeVisible();

			fireEvent.click(screen.getByRole("button", { name: "Remove run 0" }));

			expect(container.querySelectorAll('[data-slot="card"]')).toHaveLength(0);
			hoverBar(svgB, within(chartB).getByTestId("bar-rect-run-1"));
			expect(within(chartB).getByRole("link", { name: "run-1" })).toBeVisible();
			expect(container.querySelectorAll('[data-slot="card"]')).toHaveLength(1);
			act(() => {
				vi.advanceTimersByTime(500);
			});
			expect(within(chartB).getByRole("link", { name: "run-1" })).toBeVisible();
			expect(within(chartA).queryByRole("link", { name: "run-0" })).toBeNull();
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
			fireEvent.mouseMove(card);
			act(() => {
				vi.advanceTimersByTime(1000);
			});

			expect(getTooltipRunLink("run-0")).toHaveAttribute(
				"href",
				"/runs/flow-run/run-0",
			);
			expect(getTooltipRunLink("run-1")).not.toBeInTheDocument();

			fireEvent.mouseOut(card, { relatedTarget: svg });
			hoverBar(svg, screen.getByTestId("bar-rect-run-1"));
			act(() => {
				vi.advanceTimersByTime(150);
			});
			expect(getTooltipRunLink("run-1")).toBeVisible();
		});

		it("does not switch runs while the tooltip is closing", async () => {
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
			fireEvent.mouseOut(svg, { relatedTarget: card });
			act(() => {
				vi.advanceTimersByTime(1000);
			});
			expect(getTooltipRunLink("run-0")).toBeVisible();

			fireEvent.mouseOut(card, { relatedTarget: document.body });
			act(() => {
				vi.advanceTimersByTime(160);
			});
			expect(getTooltipRunLink("run-0")).toBeVisible();
			expect(getTooltipRunLink("run-1")).not.toBeInTheDocument();

			act(() => {
				vi.advanceTimersByTime(40);
			});
			expect(getTooltipRunLink("run-0")).not.toBeInTheDocument();

			hoverBar(svg, screen.getByTestId("bar-rect-run-1"));
			expect(getTooltipRunLink("run-1")).toBeVisible();
		});

		it("resumes following runs when the chart is re-entered during close", async () => {
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
			fireEvent.mouseOut(svg, { relatedTarget: card });
			act(() => {
				vi.advanceTimersByTime(1000);
			});
			fireEvent.mouseOut(card, { relatedTarget: document.body });
			act(() => {
				vi.advanceTimersByTime(100);
			});

			hoverBar(svg, screen.getByTestId("bar-rect-run-1"));
			act(() => {
				vi.advanceTimersByTime(80);
			});
			act(() => {
				vi.advanceTimersByTime(150);
			});

			expect(getTooltipRunLink("run-0")).not.toBeInTheDocument();
			expect(getTooltipRunLink("run-1")).toBeVisible();
		});

		it("keeps the current run while closing after a brief chart re-entry", async () => {
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
			fireEvent.mouseOut(svg, { relatedTarget: card });
			act(() => {
				vi.advanceTimersByTime(1000);
			});
			fireEvent.mouseOut(card, { relatedTarget: document.body });
			act(() => {
				vi.advanceTimersByTime(100);
			});

			hoverBar(svg, screen.getByTestId("bar-rect-run-1"));
			act(() => {
				vi.advanceTimersByTime(50);
			});
			fireEvent.mouseOut(svg, { relatedTarget: document.body });
			act(() => {
				vi.advanceTimersByTime(30);
			});
			act(() => {
				vi.advanceTimersByTime(150);
			});

			expect(getTooltipRunLink("run-0")).toBeVisible();
			expect(getTooltipRunLink("run-1")).not.toBeInTheDocument();
			act(() => {
				vi.advanceTimersByTime(20);
			});
			expect(getTooltipRunLink("run-0")).not.toBeInTheDocument();
			expect(getTooltipRunLink("run-1")).not.toBeInTheDocument();
		});

		it("dismisses the tooltip when Escape is pressed", async () => {
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
			fireEvent.mouseOut(svg, { relatedTarget: card });
			act(() => {
				vi.advanceTimersByTime(1000);
			});
			expect(link).toBeVisible();

			fireEvent.keyDown(document, { key: "Escape" });
			act(() => {
				vi.advanceTimersByTime(500);
			});

			expect(link).not.toBeInTheDocument();
			expect(getTooltipRunLink("run-1")).not.toBeInTheDocument();

			hoverBar(svg, screen.getByTestId("bar-rect-run-2"));
			expect(getTooltipRunLink("run-0")).not.toBeInTheDocument();
			expect(getTooltipRunLink("run-1")).not.toBeInTheDocument();
			act(() => {
				vi.advanceTimersByTime(150);
			});
			expect(getTooltipRunLink("run-2")).toBeVisible();

			hoverBar(svg, screen.getByTestId("bar-rect-run-0"));
			act(() => {
				vi.advanceTimersByTime(150);
			});
			expect(getTooltipRunLink("run-0")).toBeVisible();
		});

		it("releases shared tooltip ownership when Escape is pressed", async () => {
			const { container } = await renderWithRouter(
				<FlowRunActivityBarGraphTooltipProvider>
					<div data-testid="escape-chart-a">
						{/* @ts-expect-error - Type error from test data not matching schema */}
						<FlowRunActivityBarChart chartId="a" {...tooltipProps} />
					</div>
					<div data-testid="escape-chart-b">
						{/* @ts-expect-error - Type error from test data not matching schema */}
						<FlowRunActivityBarChart chartId="b" {...tooltipProps} />
					</div>
				</FlowRunActivityBarGraphTooltipProvider>,
			);
			const chartA = within(screen.getByTestId("escape-chart-a"));
			const chartB = within(screen.getByTestId("escape-chart-b"));
			const svgA = getSvg(screen.getByTestId("escape-chart-a"));
			const svgB = getSvg(screen.getByTestId("escape-chart-b"));

			hoverBar(svgA, chartA.getByTestId("bar-rect-run-0"));
			expect(chartA.getByRole("link", { name: "run-0" })).toBeVisible();

			fireEvent.keyDown(document, { key: "Escape" });
			expect(container.querySelectorAll('[data-slot="card"]')).toHaveLength(0);

			hoverBar(svgB, chartB.getByTestId("bar-rect-run-1"));

			expect(chartA.queryByRole("link", { name: "run-0" })).toBeNull();
			expect(chartB.getByRole("link", { name: "run-1" })).toBeVisible();
			expect(container.querySelectorAll('[data-slot="card"]')).toHaveLength(1);
		});

		it("cancels a pending close timer when Escape is pressed", async () => {
			const { container } = await renderWithRouter(
				/* @ts-expect-error - Type error from test data not matching schema */
				<FlowRunActivityBarChart {...tooltipProps} />,
			);
			const svg = getSvg(container);

			hoverBar(svg, screen.getByTestId("bar-rect-run-0"));
			const firstLink = getTooltipRunLink("run-0");
			if (!firstLink) throw new Error("tooltip did not open");
			const firstCard = firstLink.closest('[data-slot="card"]');
			if (!firstCard) throw new Error("tooltip card not found");
			hoverBar(svg, screen.getByTestId("bar-rect-run-1"));
			fireEvent.mouseOut(svg, { relatedTarget: firstCard });
			fireEvent.mouseOut(firstCard, { relatedTarget: document.body });
			act(() => {
				vi.advanceTimersByTime(100);
			});
			fireEvent.keyDown(document, { key: "Escape" });

			hoverBar(svg, screen.getByTestId("bar-rect-run-2"));
			const nextLink = getTooltipRunLink("run-2");
			if (!nextLink) throw new Error("next tooltip did not open");
			const nextCard = nextLink.closest('[data-slot="card"]');
			if (!nextCard) throw new Error("next tooltip card not found");
			hoverBar(svg, screen.getByTestId("bar-rect-run-3"));
			fireEvent.mouseOut(svg, { relatedTarget: nextCard });
			act(() => {
				vi.advanceTimersByTime(500);
			});

			expect(getTooltipRunLink("run-2")).toBeVisible();
			expect(getTooltipRunLink("run-3")).not.toBeInTheDocument();
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
