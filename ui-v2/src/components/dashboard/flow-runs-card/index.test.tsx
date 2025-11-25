import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import { buildFilterFlowRunsQuery } from "@/api/flow-runs";
import { createFakeFlowRun } from "@/mocks";
import { FlowRunsCard } from "./index";

// Wraps component in test with a Tanstack router provider
const FlowRunsCardRouter = ({
	filter,
}: {
	filter?: {
		startDate?: string;
		endDate?: string;
		tags?: string[];
		hideSubflows?: boolean;
	};
}) => {
	const rootRoute = createRootRoute({
		component: () => <FlowRunsCard filter={filter} />,
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
			createFakeFlowRun({ name: "Flow Run 1" }),
			createFakeFlowRun({ name: "Flow Run 2" }),
			createFakeFlowRun({ name: "Flow Run 3" }),
		];

		const queryClient = new QueryClient();
		const queryOptions = buildFilterFlowRunsQuery({
			sort: "START_TIME_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);

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

	it("shows empty message when no flow runs", async () => {
		const queryClient = new QueryClient();
		const queryOptions = buildFilterFlowRunsQuery({
			sort: "START_TIME_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, []);

		const wrapper = createWrapper({ queryClient });

		render(<FlowRunsCardRouter />, { wrapper });

		expect(await screen.findByText("No flow runs found")).toBeInTheDocument();
	});

	it("shows loading skeleton when flow runs exist but chart is loading", async () => {
		const flowRuns = [createFakeFlowRun()];

		const queryClient = new QueryClient();
		const queryOptions = buildFilterFlowRunsQuery({
			sort: "START_TIME_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);

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
			}),
		];

		const queryClient = new QueryClient();
		const queryOptions = buildFilterFlowRunsQuery({
			sort: "START_TIME_DESC",
			offset: 0,
			flow_runs: {
				operator: "and_",
				start_time: {
					after_: startDate,
					before_: endDate,
				},
			},
		});
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);

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
			}),
		];

		const queryClient = new QueryClient();
		const queryOptions = buildFilterFlowRunsQuery({
			sort: "START_TIME_DESC",
			offset: 0,
			flow_runs: {
				operator: "and_",
				tags: {
					operator: "and_",
					all_: ["production", "critical"],
				},
			},
		});
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);

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
			}),
		];

		const queryClient = new QueryClient();
		const queryOptions = buildFilterFlowRunsQuery({
			sort: "START_TIME_DESC",
			offset: 0,
			flow_runs: {
				operator: "and_",
				parent_task_run_id: {
					operator: "and_",
					is_null_: true,
				},
			},
		});
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);

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
			}),
		];

		const queryClient = new QueryClient();
		const queryOptions = buildFilterFlowRunsQuery({
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
		});
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);

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
		const flowRuns = [createFakeFlowRun()];

		const queryClient = new QueryClient();
		const queryOptions = buildFilterFlowRunsQuery({
			sort: "START_TIME_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);

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
			createFakeFlowRun(),
			createFakeFlowRun({ parent_task_run_id: "some-parent-id" }),
		];

		const queryClient = new QueryClient();
		const queryOptions = buildFilterFlowRunsQuery({
			sort: "START_TIME_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);

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
		const flowRuns = [createFakeFlowRun()];

		const queryClient = new QueryClient();
		const queryOptions = buildFilterFlowRunsQuery({
			sort: "START_TIME_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, flowRuns);

		const wrapper = createWrapper({ queryClient });

		render(<FlowRunsCardRouter />, { wrapper });

		expect(await screen.findByText("Flow Runs")).toBeInTheDocument();
		expect(screen.getByText("1 total")).toBeInTheDocument();
	});
});
