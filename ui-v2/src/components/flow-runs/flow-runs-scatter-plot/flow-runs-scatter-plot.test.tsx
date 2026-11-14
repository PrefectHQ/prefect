import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRoute,
	createRouter,
	Outlet,
	RouterProvider,
} from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { type ComponentProps, type ReactNode, useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SimpleFlowRun } from "@/api/flow-runs";
import type { StateType } from "@/api/flow-runs/constants";
import { STATE_TYPES } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filter-utils";
import {
	createFakeFlow,
	createFakeFlowRun,
	createFakeSimpleFlowRun,
} from "@/mocks";
import { FlowRunsScatterPlot } from "./flow-runs-scatter-plot";

// tests/setup.ts sizes every element 500x300, which places the plot's x range
// at [52, 482] and the zero-duration lane at y = 272.
const START = new Date("2026-11-06T00:00:00Z");
const END = new Date("2026-11-06T10:00:00Z");
const MIDDLE_X = (52 + 482) / 2;
const LANE_Y = 272;

const crashed = createFakeSimpleFlowRun({
	id: "crashed-run",
	state_type: "CRASHED",
	timestamp: "2026-11-06T05:00:00Z",
	duration: 0,
	lateness: 0,
});
const completed = createFakeSimpleFlowRun({
	id: "completed-run",
	state_type: "COMPLETED",
	timestamp: "2026-11-06T02:00:00Z",
	duration: 119,
	lateness: 0,
});

type PlotProps = ComponentProps<typeof FlowRunsScatterPlot>;

const PlotWithStateFilter = ({
	selectedStateTypes: initialTypes,
	onSelectedStateTypesChange,
	...props
}: PlotProps) => {
	const [selectedStateTypes, setSelectedStateTypes] = useState(
		() => new Set(initialTypes),
	);
	return (
		<FlowRunsScatterPlot
			{...props}
			selectedStateTypes={selectedStateTypes}
			onSelectedStateTypesChange={(types) => {
				onSelectedStateTypesChange?.(types);
				setSelectedStateTypes(types);
			}}
		/>
	);
};

const renderPlot = (
	props: Partial<PlotProps> = {},
	Plot: (props: PlotProps) => ReactNode = PlotWithStateFilter,
) => {
	const rootRoute = createRootRoute({ component: Outlet });
	const plotRoute = createRoute({
		getParentRoute: () => rootRoute,
		path: "/",
		component: () => (
			<Plot
				history={[completed, crashed]}
				startDate={START}
				endDate={END}
				{...props}
			/>
		),
	});
	const runRoute = createRoute({
		getParentRoute: () => rootRoute,
		path: "/runs/flow-run/$id",
		component: () => <p>run page</p>,
	});
	const router = createRouter({
		routeTree: rootRoute.addChildren([plotRoute, runRoute]),
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});
	render(<RouterProvider router={router} />, { wrapper: createWrapper() });
	return router;
};

const pointer = (
	type: "pointerDown" | "pointerMove" | "pointerUp",
	target: Element,
	init: { x: number; y: number; pointerType: "mouse" | "touch" },
) =>
	fireEvent[type](target, {
		pointerId: 1,
		pointerType: init.pointerType,
		button: 0,
		clientX: init.x,
		clientY: init.y,
	});

describe("FlowRunsScatterPlot", () => {
	beforeEach(() => {
		HTMLElement.prototype.setPointerCapture = vi.fn();
		server.use(
			http.get(buildApiUrl("/flow_runs/:id"), ({ params }) =>
				HttpResponse.json(
					createFakeFlowRun({
						id: String(params.id),
						name: "brave-otter",
						flow_id: "flow-1",
					}),
				),
			),
			http.get(buildApiUrl("/flows/:id"), () =>
				HttpResponse.json(
					createFakeFlow({ id: "flow-1", name: "nightly-etl" }),
				),
			),
		);
	});

	it("summarizes the window and counts each state", async () => {
		renderPlot();

		expect(
			await screen.findByRole("button", { name: /Completed\s*1/ }),
		).toBeVisible();
		expect(screen.getByRole("button", { name: /Crashed\s*1/ })).toBeVisible();
		expect(screen.getByTestId("scatter-plot-readout")).toHaveTextContent(
			"2 runs · median 1m 59s · p90 1m 59s",
		);
	});

	it("says when the row limit left older runs out", async () => {
		renderPlot({ totalCount: 7432, onRangeChange: vi.fn() });

		const readout = await screen.findByTestId("scatter-plot-readout");
		expect(readout).toHaveTextContent("Latest 2 of 7,432 runs, since");
		expect(readout).toHaveTextContent(
			"Narrow the date range to load older runs.",
		);
	});

	it("does not call a full page complete while the run count is still 0", async () => {
		const fullPage = Array.from({ length: 1000 }, (_, index) =>
			createFakeSimpleFlowRun({
				timestamp: new Date(END.getTime() - index * 30_000).toISOString(),
				duration: 1,
			}),
		);
		renderPlot({ history: fullPage, totalCount: 0 });

		expect(await screen.findByTestId("scatter-plot-readout")).toHaveTextContent(
			"Latest 1,000 of more than 1,000 runs, since",
		);
	});

	it("falls back to a short id when the run's details fail to load", async () => {
		server.use(
			http.get(buildApiUrl("/flow_runs/:id"), () =>
				HttpResponse.json({ detail: "gone" }, { status: 404 }),
			),
		);
		const user = userEvent.setup();
		renderPlot();

		(await screen.findByRole("img")).focus();
		await user.keyboard("{End}");

		expect(await screen.findByText("crashed-")).toBeVisible();
	});

	it("shows a skeleton instead of a count while loading", async () => {
		renderPlot({ history: undefined });

		await screen.findByTestId("scatter-plot");
		expect(screen.queryByTestId("scatter-plot-readout")).toBeNull();
	});

	it("says so when the window has no runs", async () => {
		renderPlot({ history: [] });

		expect(
			await screen.findByText("No flow runs in this window"),
		).toBeVisible();
		expect(screen.getByRole("img")).toHaveAttribute("tabindex", "-1");
	});

	it("steps through runs in time order from the keyboard", async () => {
		const user = userEvent.setup();
		renderPlot();

		const plot = await screen.findByRole("img");
		plot.focus();
		await user.keyboard("{Home}");

		const readout = screen.getByTestId("scatter-plot-readout");
		expect(readout).toHaveTextContent("1m 59s");
		expect(await screen.findByText("nightly-etl")).toBeVisible();
		expect(screen.getByText("brave-otter")).toBeVisible();

		await user.keyboard("{ArrowRight}");
		expect(readout).toHaveTextContent("0s");

		await user.keyboard("{Escape}");
		expect(readout).toHaveTextContent("2 runs");
	});

	it("opens the selected run with Enter", async () => {
		const user = userEvent.setup();
		const router = renderPlot();

		const plot = await screen.findByRole("img");
		plot.focus();
		await user.keyboard("{End}{Enter}");

		await waitFor(() =>
			expect(router.state.location.pathname).toBe("/runs/flow-run/crashed-run"),
		);
	});

	it("selects a run on tap and clears it on an empty tap", async () => {
		renderPlot();

		const plot = await screen.findByRole("img");
		const readout = screen.getByTestId("scatter-plot-readout");
		const tap = (x: number, y: number) => {
			pointer("pointerDown", plot, { x, y, pointerType: "touch" });
			pointer("pointerUp", plot, { x, y, pointerType: "touch" });
		};

		tap(MIDDLE_X + 10, LANE_Y - 10);
		expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute(
			"href",
			"/runs/flow-run/crashed-run",
		);

		tap(60, 20);
		expect(readout).toHaveTextContent("2 runs");
	});

	it("opens a run on mouse click", async () => {
		const router = renderPlot();

		const plot = await screen.findByRole("img");
		pointer("pointerMove", plot, {
			x: MIDDLE_X,
			y: LANE_Y,
			pointerType: "mouse",
		});
		expect(screen.getByTestId("scatter-plot-readout")).toHaveTextContent("0s");
		pointer("pointerDown", plot, {
			x: MIDDLE_X,
			y: LANE_Y,
			pointerType: "mouse",
		});
		pointer("pointerUp", plot, {
			x: MIDDLE_X,
			y: LANE_Y,
			pointerType: "mouse",
		});

		await waitFor(() =>
			expect(router.state.location.pathname).toBe("/runs/flow-run/crashed-run"),
		);
	});

	it("zooms to the span dragged across", async () => {
		const onRangeChange =
			vi.fn<(range: { startDate: Date; endDate: Date }) => void>();
		renderPlot({ onRangeChange });

		const plot = await screen.findByRole("img");
		pointer("pointerDown", plot, { x: 52, y: 100, pointerType: "mouse" });
		pointer("pointerMove", plot, { x: 200, y: 104, pointerType: "mouse" });
		pointer("pointerMove", plot, {
			x: MIDDLE_X,
			y: 104,
			pointerType: "mouse",
		});
		pointer("pointerUp", plot, { x: MIDDLE_X, y: 104, pointerType: "mouse" });

		expect(onRangeChange).toHaveBeenCalledTimes(1);
		const [{ startDate, endDate }] = onRangeChange.mock.calls[0];
		expect(startDate).toEqual(START);
		expect(endDate).toEqual(new Date("2026-11-06T05:00:00Z"));
	});

	it("does not zoom on a vertical drag, which scrolls the page", async () => {
		const onRangeChange = vi.fn();
		renderPlot({ onRangeChange });

		const plot = await screen.findByRole("img");
		pointer("pointerDown", plot, { x: 200, y: 50, pointerType: "touch" });
		pointer("pointerMove", plot, { x: 212, y: 150, pointerType: "touch" });
		pointer("pointerUp", plot, { x: 212, y: 150, pointerType: "touch" });

		expect(onRangeChange).not.toHaveBeenCalled();
	});

	it("filters to one state from the legend and restores the filter", async () => {
		const user = userEvent.setup();
		const onSelectedStateTypesChange = vi.fn<(types: Set<StateType>) => void>();
		renderPlot({
			selectedStateTypes: new Set(["COMPLETED", "CRASHED"]),
			onSelectedStateTypesChange,
		});

		const chip = await screen.findByRole("button", { name: /Crashed/ });
		await user.click(chip);
		expect(onSelectedStateTypesChange).toHaveBeenLastCalledWith(
			new Set(["CRASHED"]),
		);
		expect(chip).toHaveAttribute("aria-pressed", "true");

		await user.click(chip);
		expect(onSelectedStateTypesChange).toHaveBeenLastCalledWith(
			new Set(["COMPLETED", "CRASHED"]),
		);
		expect(chip).toHaveAttribute("aria-pressed", "false");
	});

	it("restores the filter from before the first chip after switching chips", async () => {
		const user = userEvent.setup();
		const onSelectedStateTypesChange = vi.fn<(types: Set<StateType>) => void>();
		renderPlot({
			selectedStateTypes: new Set(["COMPLETED", "CRASHED"]),
			onSelectedStateTypesChange,
		});

		await user.click(await screen.findByRole("button", { name: /Crashed/ }));
		const completedChip = screen.getByRole("button", { name: /Completed/ });
		await user.click(completedChip);
		expect(onSelectedStateTypesChange).toHaveBeenLastCalledWith(
			new Set(["COMPLETED"]),
		);

		await user.click(completedChip);
		expect(onSelectedStateTypesChange).toHaveBeenLastCalledWith(
			new Set(["COMPLETED", "CRASHED"]),
		);
		expect(completedChip).toHaveAttribute("aria-pressed", "false");
	});

	it("keeps a chip for every counted state while one is selected", async () => {
		const user = userEvent.setup();
		const onSelectedStateTypesChange = vi.fn<(types: Set<StateType>) => void>();
		const counted = (
			state_type: "COMPLETED" | "CRASHED",
			count_runs: number,
		) => ({
			state_type,
			state_name: state_type.charAt(0) + state_type.slice(1).toLowerCase(),
			count_runs,
			sum_estimated_run_time: 0,
			sum_estimated_lateness: 0,
		});
		renderPlot({
			history: [crashed],
			selectedStateTypes: new Set(["CRASHED"]),
			onSelectedStateTypesChange,
			stateHistory: [
				{
					interval_start: START.toISOString(),
					interval_end: END.toISOString(),
					states: [counted("COMPLETED", 40), counted("CRASHED", 1)],
				},
			],
		});

		expect(
			await screen.findByRole("button", { name: /Crashed\s*1/ }),
		).toHaveAttribute("aria-pressed", "true");
		const completedChip = screen.getByRole("button", {
			name: /Completed\s*40/,
		});
		expect(completedChip).toHaveAttribute("aria-pressed", "false");

		await user.click(completedChip);
		expect(onSelectedStateTypesChange).toHaveBeenLastCalledWith(
			new Set(["COMPLETED"]),
		);
	});

	it("hides a state on shift-click", async () => {
		const user = userEvent.setup();
		const onSelectedStateTypesChange = vi.fn<(types: Set<StateType>) => void>();
		renderPlot({ onSelectedStateTypesChange });

		await user.keyboard("{Shift>}");
		await user.click(await screen.findByRole("button", { name: /Completed/ }));

		const [types] = onSelectedStateTypesChange.mock.lastCall ?? [];
		expect(types?.has("COMPLETED")).toBe(false);
		expect(types?.has("CRASHED")).toBe(true);
		expect(types?.size).toBe(STATE_TYPES.length - 1);
	});

	it("shows a plain key when it cannot set the filter", async () => {
		renderPlot({}, FlowRunsScatterPlot);

		expect(await screen.findByText("Completed")).toBeVisible();
		expect(screen.queryByRole("button", { name: /Completed/ })).toBeNull();
	});

	it("leaves out runs scheduled after an open-ended window", async () => {
		const scheduled: SimpleFlowRun = createFakeSimpleFlowRun({
			state_type: "SCHEDULED",
			timestamp: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString(),
			duration: 0,
		});
		renderPlot({
			history: [
				{
					...completed,
					timestamp: new Date(Date.now() - 60_000).toISOString(),
				},
				scheduled,
			],
			startDate: undefined,
			endDate: undefined,
		});

		expect(
			await screen.findByText(/1 more scheduled after this window\./),
		).toBeVisible();
		expect(screen.getByTestId("scatter-plot-readout")).toHaveTextContent(
			"1 run",
		);
		expect(screen.queryByRole("button", { name: /Scheduled/ })).toBeNull();
	});
});
