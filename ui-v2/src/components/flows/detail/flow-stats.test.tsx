import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { queryKeyFactory as flowRunsQueryKeyFactory } from "@/api/flow-runs";
import {
	buildCountTaskRunsQuery,
	type TaskRunsCountFilter,
} from "@/api/task-runs";
import { FlowStats } from "./flow-stats";

const TEST_FLOW_ID = "test-flow-id";
const REFETCH_INTERVAL = 30_000;
const MOCK_DATE = "2024-01-15T00:00:00.000Z";

beforeEach(() => {
	vi.useFakeTimers({ shouldAdvanceTime: true });
	vi.setSystemTime(new Date(MOCK_DATE));
});

afterEach(() => {
	vi.useRealTimers();
});

const FlowStatsRouter = ({
	flowId,
	queryClient,
}: {
	flowId: string;
	queryClient: QueryClient;
}) => {
	const rootRoute = createRootRoute({
		component: () => <FlowStats flowId={flowId} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient },
	});
	return <RouterProvider router={router} />;
};

const setupFlowStatsQueries = (
	queryClient: QueryClient,
	flowId: string,
	counts: {
		flowRuns: number;
		totalTaskRuns: number;
		completedTaskRuns: number;
		failedTaskRuns: number;
	},
) => {
	queryClient.setQueryData(
		flowRunsQueryKeyFactory.countByFlowPastWeek(flowId),
		counts.flowRuns,
	);

	const totalTaskRunsFilter: TaskRunsCountFilter = {
		flows: {
			operator: "and_",
			id: { any_: [flowId] },
		},
		task_runs: {
			operator: "and_",
			state: {
				operator: "and_",
				type: { any_: ["COMPLETED", "FAILED", "CRASHED", "RUNNING"] },
			},
		},
	};

	const completedTaskRunsFilter: TaskRunsCountFilter = {
		flows: {
			operator: "and_",
			id: { any_: [flowId] },
		},
		task_runs: {
			operator: "and_",
			state: {
				operator: "and_",
				type: { any_: ["COMPLETED"] },
			},
		},
	};

	const failedTaskRunsFilter: TaskRunsCountFilter = {
		flows: {
			operator: "and_",
			id: { any_: [flowId] },
		},
		task_runs: {
			operator: "and_",
			state: {
				operator: "and_",
				type: { any_: ["FAILED", "CRASHED"] },
			},
		},
	};

	queryClient.setQueryData(
		buildCountTaskRunsQuery(totalTaskRunsFilter, REFETCH_INTERVAL).queryKey,
		counts.totalTaskRuns,
	);

	queryClient.setQueryData(
		buildCountTaskRunsQuery(completedTaskRunsFilter, REFETCH_INTERVAL).queryKey,
		counts.completedTaskRuns,
	);

	queryClient.setQueryData(
		buildCountTaskRunsQuery(failedTaskRunsFilter, REFETCH_INTERVAL).queryKey,
		counts.failedTaskRuns,
	);
};

describe("FlowStats", () => {
	it("renders flow stats with all four cards", async () => {
		const queryClient = new QueryClient();
		setupFlowStatsQueries(queryClient, TEST_FLOW_ID, {
			flowRuns: 10,
			totalTaskRuns: 100,
			completedTaskRuns: 80,
			failedTaskRuns: 20,
		});

		const wrapper = createWrapper({ queryClient });

		render(
			<FlowStatsRouter flowId={TEST_FLOW_ID} queryClient={queryClient} />,
			{
				wrapper,
			},
		);

		expect(
			await screen.findByText("Flow Runs (Past Week)"),
		).toBeInTheDocument();
		expect(screen.getByText("Total Task Runs")).toBeInTheDocument();
		expect(screen.getByText("Completed Task Runs")).toBeInTheDocument();
		expect(screen.getByText("Failed Task Runs")).toBeInTheDocument();
	});

	it("displays correct flow runs count", async () => {
		const queryClient = new QueryClient();
		setupFlowStatsQueries(queryClient, TEST_FLOW_ID, {
			flowRuns: 42,
			totalTaskRuns: 100,
			completedTaskRuns: 80,
			failedTaskRuns: 20,
		});

		const wrapper = createWrapper({ queryClient });

		render(
			<FlowStatsRouter flowId={TEST_FLOW_ID} queryClient={queryClient} />,
			{
				wrapper,
			},
		);

		expect(await screen.findByTestId("flow-runs-count")).toHaveTextContent(
			"42",
		);
	});

	it("displays correct task runs counts", async () => {
		const queryClient = new QueryClient();
		setupFlowStatsQueries(queryClient, TEST_FLOW_ID, {
			flowRuns: 10,
			totalTaskRuns: 150,
			completedTaskRuns: 120,
			failedTaskRuns: 30,
		});

		const wrapper = createWrapper({ queryClient });

		render(
			<FlowStatsRouter flowId={TEST_FLOW_ID} queryClient={queryClient} />,
			{
				wrapper,
			},
		);

		expect(await screen.findByTestId("total-task-runs")).toHaveTextContent(
			"150",
		);
		expect(screen.getByTestId("completed-task-runs")).toHaveTextContent("120");
		expect(screen.getByTestId("failed-task-runs")).toHaveTextContent("30");
	});

	it("displays zero counts correctly", async () => {
		const queryClient = new QueryClient();
		setupFlowStatsQueries(queryClient, TEST_FLOW_ID, {
			flowRuns: 0,
			totalTaskRuns: 0,
			completedTaskRuns: 0,
			failedTaskRuns: 0,
		});

		const wrapper = createWrapper({ queryClient });

		render(
			<FlowStatsRouter flowId={TEST_FLOW_ID} queryClient={queryClient} />,
			{
				wrapper,
			},
		);

		expect(await screen.findByTestId("flow-runs-count")).toHaveTextContent("0");
		expect(screen.getByTestId("total-task-runs")).toHaveTextContent("0");
		expect(screen.getByTestId("completed-task-runs")).toHaveTextContent("0");
		expect(screen.getByTestId("failed-task-runs")).toHaveTextContent("0");
	});

	it("renders with different flow ID", async () => {
		const differentFlowId = "different-flow-id";
		const queryClient = new QueryClient();
		setupFlowStatsQueries(queryClient, differentFlowId, {
			flowRuns: 5,
			totalTaskRuns: 50,
			completedTaskRuns: 45,
			failedTaskRuns: 5,
		});

		const wrapper = createWrapper({ queryClient });

		render(
			<FlowStatsRouter flowId={differentFlowId} queryClient={queryClient} />,
			{ wrapper },
		);

		expect(await screen.findByTestId("flow-runs-count")).toHaveTextContent("5");
		expect(screen.getByTestId("total-task-runs")).toHaveTextContent("50");
	});
});
