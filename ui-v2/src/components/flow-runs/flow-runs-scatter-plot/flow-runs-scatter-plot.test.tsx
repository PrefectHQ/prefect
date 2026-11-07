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
import type { ComponentProps } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import type { SimpleFlowRun } from "@/api/flow-runs";
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

const renderPlot = (props: Partial<PlotProps> = {}) => {
	const rootRoute = createRootRoute({ component: Outlet });
	const plotRoute = createRoute({
		getParentRoute: () => rootRoute,
		path: "/",
		component: () => (
			<FlowRunsScatterPlot
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

		const legend = await screen.findByRole("list", { name: "Runs by state" });
		expect(legend).toHaveTextContent("Completed1Crashed1");
		expect(screen.getByTestId("scatter-plot-readout")).toHaveTextContent(
			"2 runs · median 1m 59s · p90 1m 59s",
		);
	});

	it("says when the row limit left older runs out", async () => {
		renderPlot({ totalCount: 7432 });

		const readout = await screen.findByTestId("scatter-plot-readout");
		expect(readout).toHaveTextContent("Latest 2 of 7,432 runs, since");
		expect(readout).toHaveTextContent(
			"Narrow the date range to load older runs.",
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
		expect(
			screen.getByRole("list", { name: "Runs by state" }),
		).not.toHaveTextContent("Scheduled");
	});
});
