import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import {
	buildCountFlowRunsQuery,
	buildFilterFlowRunsQuery,
	type FlowRunsFilter,
	toFlowRunsCountFilter,
} from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import { createFakeFlowRun } from "@/mocks";
import { FlowRunsCard } from "./index";

// Helper to set up all count queries needed by FlowRunsCard
const setupCountQueries = (
	queryClient: QueryClient,
	filter: FlowRunsFilter,
	counts: {
		total?: number;
		failedCrashed?: number;
		runningPendingCancelling?: number;
		completed?: number;
		scheduledPaused?: number;
		cancelled?: number;
	} = {},
) => {
	const countFilter = toFlowRunsCountFilter(filter);

	// Total count
	queryClient.setQueryData(
		buildCountFlowRunsQuery(countFilter, 30000).queryKey,
		counts.total ?? 0,
	);

	// Failed + Crashed count
	queryClient.setQueryData(
		buildCountFlowRunsQuery(
			{
				...countFilter,
				flow_runs: {
					...countFilter.flow_runs,
					operator: countFilter.flow_runs?.operator ?? "and_",
					state: { operator: "and_", type: { any_: ["FAILED", "CRASHED"] } },
				},
			},
			30000,
		).queryKey,
		counts.failedCrashed ?? 0,
	);

	// Running + Pending + Cancelling count
	queryClient.setQueryData(
		buildCountFlowRunsQuery(
			{
				...countFilter,
				flow_runs: {
					...countFilter.flow_runs,
					operator: countFilter.flow_runs?.operator ?? "and_",
					state: {
						operator: "and_",
						type: { any_: ["RUNNING", "PENDING", "CANCELLING"] },
					},
				},
			},
			30000,
		).queryKey,
		counts.runningPendingCancelling ?? 0,
	);

	// Completed count
	queryClient.setQueryData(
		buildCountFlowRunsQuery(
			{
				...countFilter,
				flow_runs: {
					...countFilter.flow_runs,
					operator: countFilter.flow_runs?.operator ?? "and_",
					state: { operator: "and_", type: { any_: ["COMPLETED"] } },
				},
			},
			30000,
		).queryKey,
		counts.completed ?? 0,
	);

	// Scheduled + Paused count
	queryClient.setQueryData(
		buildCountFlowRunsQuery(
			{
				...countFilter,
				flow_runs: {
					...countFilter.flow_runs,
					operator: countFilter.flow_runs?.operator ?? "and_",
					state: { operator: "and_", type: { any_: ["SCHEDULED", "PAUSED"] } },
				},
			},
			30000,
		).queryKey,
		counts.scheduledPaused ?? 0,
	);

	// Cancelled count
	queryClient.setQueryData(
		buildCountFlowRunsQuery(
			{
				...countFilter,
				flow_runs: {
					...countFilter.flow_runs,
					operator: countFilter.flow_runs?.operator ?? "and_",
					state: { operator: "and_", type: { any_: ["CANCELLED"] } },
				},
			},
			30000,
		).queryKey,
		counts.cancelled ?? 0,
	);
};

type StateType = components["schemas"]["StateType"];

// Wraps component in test with a Tanstack router provider
const FlowRunsCardRouter = ({
	filter,
	selectedStates,
	onStateChange,
}: {
	filter?: {
		startDate?: string;
		endDate?: string;
		tags?: string[];
		hideSubflows?: boolean;
	};
	selectedStates?: StateType[];
	onStateChange?: (states: StateType[]) => void;
}) => {
	const rootRoute = createRootRoute({
		component: () => (
			<FlowRunsCard
				filter={filter}
				selectedStates={selectedStates}
				onStateChange={onStateChange}
			/>
		),
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

describe("FlowRunsCard", () => {
	it("renders flow runs card with title", async () => {
		const flowRun1 = createFakeFlowRun({ name: "Flow Run 1" });
		const flowRun2 = createFakeFlowRun({ name: "Flow Run 2" });

		const queryClient = new QueryClient();
		const queryOptions = buildFilterFlowRunsQuery({
			sort: "START_TIME_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, [flowRun1, flowRun2]);

		const wrapper = createWrapper({ queryClient });

		render(<FlowRunsCardRouter />, { wrapper });

		expect(await screen.findByText("Flow Runs")).toBeInTheDocument();
	});

	it("displays total count when flow runs exist", async () => {
		const flowRuns = [
			createFakeFlowRun({ name: "Flow Run 1", state_type: "FAILED" }),
			createFakeFlowRun({ name: "Flow Run 2", state_type: "FAILED" }),
			createFakeFlowRun({ name: "Flow Run 3", state_type: "FAILED" }),
		];

		const queryClient = new QueryClient();
		const filter: FlowRunsFilter = {
			sort: "START_TIME_DESC",
			offset: 0,
		};
		const queryOptions = buildFilterFlowRunsQuery(filter);
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);
		setupCountQueries(queryClient, filter, { total: 3, failedCrashed: 3 });

		const wrapper = createWrapper({ queryClient });

		render(<FlowRunsCardRouter />, { wrapper });

		expect(await screen.findByText("3 total")).toBeInTheDocument();
	});

	it("does not display count when no flow runs exist", async () => {
		const queryClient = new QueryClient();
		const queryOptions = buildFilterFlowRunsQuery({
			sort: "START_TIME_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, []);

		const wrapper = createWrapper({ queryClient });

		render(<FlowRunsCardRouter />, { wrapper });

		expect(await screen.findByText("Flow Runs")).toBeInTheDocument();
		expect(screen.queryByText("total")).not.toBeInTheDocument();
	});

	it("shows chart and state tabs when no flow runs", async () => {
		const queryClient = new QueryClient();
		const queryOptions = buildFilterFlowRunsQuery({
			sort: "START_TIME_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, []);

		const wrapper = createWrapper({ queryClient });

		render(<FlowRunsCardRouter />, { wrapper });

		// The card should still render with the title
		expect(await screen.findByText("Flow Runs")).toBeInTheDocument();
		// State tabs should be visible with 0 counts
		expect(screen.getByRole("tablist")).toBeInTheDocument();
	});

	it("shows loading skeleton when flow runs exist but chart is loading", async () => {
		const flowRuns = [createFakeFlowRun({ state_type: "FAILED" })];

		const queryClient = new QueryClient();
		const filter: FlowRunsFilter = {
			sort: "START_TIME_DESC",
			offset: 0,
		};
		const queryOptions = buildFilterFlowRunsQuery(filter);
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);
		setupCountQueries(queryClient, filter, { total: 1, failedCrashed: 1 });

		const wrapper = createWrapper({ queryClient });

		render(<FlowRunsCardRouter />, { wrapper });

		// The chart shows a skeleton while loading enrichment data or calculating bar count
		expect(
			await screen.findByRole("generic", { name: "" }),
		).toBeInTheDocument();
		expect(screen.getByText("1 total")).toBeInTheDocument();
	});

	it("applies date range filter correctly", async () => {
		const startDate = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
		const endDate = new Date().toISOString();
		const flowRuns = [
			createFakeFlowRun({
				start_time: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
				state_type: "FAILED",
			}),
		];

		const queryClient = new QueryClient();
		const filter: FlowRunsFilter = {
			sort: "START_TIME_DESC",
			offset: 0,
			flow_runs: {
				operator: "and_",
				start_time: {
					after_: startDate,
					before_: endDate,
				},
			},
		};
		const queryOptions = buildFilterFlowRunsQuery(filter);
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);
		setupCountQueries(queryClient, filter, { total: 1, failedCrashed: 1 });

		const wrapper = createWrapper({ queryClient });

		render(
			<FlowRunsCardRouter
				filter={{
					startDate,
					endDate,
				}}
			/>,
			{ wrapper },
		);

		expect(await screen.findByText("1 total")).toBeInTheDocument();
	});

	it("applies tags filter correctly", async () => {
		const flowRuns = [
			createFakeFlowRun({
				tags: ["production", "critical"],
				state_type: "FAILED",
			}),
		];

		const queryClient = new QueryClient();
		const filter: FlowRunsFilter = {
			sort: "START_TIME_DESC",
			offset: 0,
			flow_runs: {
				operator: "and_",
				tags: {
					operator: "and_",
					all_: ["production", "critical"],
				},
			},
		};
		const queryOptions = buildFilterFlowRunsQuery(filter);
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);
		setupCountQueries(queryClient, filter, { total: 1, failedCrashed: 1 });

		const wrapper = createWrapper({ queryClient });

		render(
			<FlowRunsCardRouter
				filter={{
					tags: ["production", "critical"],
				}}
			/>,
			{ wrapper },
		);

		expect(await screen.findByText("1 total")).toBeInTheDocument();
	});

	it("applies hideSubflows filter correctly", async () => {
		const flowRuns = [
			createFakeFlowRun({
				parent_task_run_id: null,
				state_type: "FAILED",
			}),
		];

		const queryClient = new QueryClient();
		const filter: FlowRunsFilter = {
			sort: "START_TIME_DESC",
			offset: 0,
			flow_runs: {
				operator: "and_",
				parent_task_run_id: {
					operator: "and_",
					is_null_: true,
				},
			},
		};
		const queryOptions = buildFilterFlowRunsQuery(filter);
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);
		setupCountQueries(queryClient, filter, { total: 1, failedCrashed: 1 });

		const wrapper = createWrapper({ queryClient });

		render(
			<FlowRunsCardRouter
				filter={{
					hideSubflows: true,
				}}
			/>,
			{ wrapper },
		);

		expect(await screen.findByText("1 total")).toBeInTheDocument();
	});

	it("applies combined filters correctly", async () => {
		const startDate = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
		const endDate = new Date().toISOString();
		const flowRuns = [
			createFakeFlowRun({
				start_time: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
				tags: ["production"],
				parent_task_run_id: null,
				state_type: "FAILED",
			}),
		];

		const queryClient = new QueryClient();
		const filter: FlowRunsFilter = {
			sort: "START_TIME_DESC",
			offset: 0,
			flow_runs: {
				operator: "and_",
				start_time: {
					after_: startDate,
					before_: endDate,
				},
				tags: {
					operator: "and_",
					all_: ["production"],
				},
				parent_task_run_id: {
					operator: "and_",
					is_null_: true,
				},
			},
		};
		const queryOptions = buildFilterFlowRunsQuery(filter);
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);
		setupCountQueries(queryClient, filter, { total: 1, failedCrashed: 1 });

		const wrapper = createWrapper({ queryClient });

		render(
			<FlowRunsCardRouter
				filter={{
					startDate,
					endDate,
					tags: ["production"],
					hideSubflows: true,
				}}
			/>,
			{ wrapper },
		);

		expect(await screen.findByText("1 total")).toBeInTheDocument();
	});

	it("handles empty tags array", async () => {
		const flowRuns = [createFakeFlowRun({ state_type: "FAILED" })];

		const queryClient = new QueryClient();
		const filter: FlowRunsFilter = {
			sort: "START_TIME_DESC",
			offset: 0,
		};
		const queryOptions = buildFilterFlowRunsQuery(filter);
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);
		setupCountQueries(queryClient, filter, { total: 1, failedCrashed: 1 });

		const wrapper = createWrapper({ queryClient });

		render(
			<FlowRunsCardRouter
				filter={{
					tags: [],
				}}
			/>,
			{ wrapper },
		);

		expect(await screen.findByText("1 total")).toBeInTheDocument();
	});

	it("handles hideSubflows false", async () => {
		const flowRuns = [
			createFakeFlowRun({ state_type: "FAILED" }),
			createFakeFlowRun({
				parent_task_run_id: "some-parent-id",
				state_type: "FAILED",
			}),
		];

		const queryClient = new QueryClient();
		const filter: FlowRunsFilter = {
			sort: "START_TIME_DESC",
			offset: 0,
		};
		const queryOptions = buildFilterFlowRunsQuery(filter);
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);
		setupCountQueries(queryClient, filter, { total: 2, failedCrashed: 2 });

		const wrapper = createWrapper({ queryClient });

		render(
			<FlowRunsCardRouter
				filter={{
					hideSubflows: false,
				}}
			/>,
			{ wrapper },
		);

		expect(await screen.findByText("2 total")).toBeInTheDocument();
	});

	it("renders with no filter prop", async () => {
		const flowRuns = [createFakeFlowRun({ state_type: "FAILED" })];

		const queryClient = new QueryClient();
		const filter: FlowRunsFilter = {
			sort: "START_TIME_DESC",
			offset: 0,
		};
		const queryOptions = buildFilterFlowRunsQuery(filter);
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);
		setupCountQueries(queryClient, filter, { total: 1, failedCrashed: 1 });

		const wrapper = createWrapper({ queryClient });

		render(<FlowRunsCardRouter />, { wrapper });

		expect(await screen.findByText("Flow Runs")).toBeInTheDocument();
		expect(screen.getByText("1 total")).toBeInTheDocument();
	});

	it("accepts controlled selectedStates and onStateChange props", async () => {
		const flowRuns = [
			createFakeFlowRun({ state_type: "COMPLETED" }),
			createFakeFlowRun({ state_type: "FAILED" }),
		];
		const onStateChange = vi.fn();

		const queryClient = new QueryClient();
		const filter: FlowRunsFilter = {
			sort: "START_TIME_DESC",
			offset: 0,
		};
		const queryOptions = buildFilterFlowRunsQuery(filter);
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);
		setupCountQueries(queryClient, filter, {
			total: 2,
			failedCrashed: 1,
			completed: 1,
		});

		const wrapper = createWrapper({ queryClient });

		render(
			<FlowRunsCardRouter
				selectedStates={["COMPLETED"]}
				onStateChange={onStateChange}
			/>,
			{ wrapper },
		);

		expect(await screen.findByText("Flow Runs")).toBeInTheDocument();
		expect(screen.getByText("2 total")).toBeInTheDocument();
	});
});
