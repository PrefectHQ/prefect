import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { FlowStats } from "./flow-stats";

const TEST_FLOW_ID = "test-flow-id";

const FlowStatsRouter = ({ flowId }: { flowId: string }) => {
	const rootRoute = createRootRoute({
		component: () => <FlowStats flowId={flowId} />,
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

const createMswHandlers = (counts: {
	flowRuns: number;
	totalTaskRuns: number;
	completedTaskRuns: number;
	failedTaskRuns: number;
}) => [
	http.post(buildApiUrl("/flow_runs/count"), () => {
		return HttpResponse.json(counts.flowRuns);
	}),
	http.post(buildApiUrl("/task_runs/count"), async ({ request }) => {
		const body = (await request.json()) as {
			task_runs?: { state?: { type?: { any_?: string[] } } };
		};
		const stateTypes = body?.task_runs?.state?.type?.any_ ?? [];

		if (stateTypes.includes("COMPLETED") && stateTypes.length === 1) {
			return HttpResponse.json(counts.completedTaskRuns);
		}
		if (
			stateTypes.includes("FAILED") &&
			stateTypes.includes("CRASHED") &&
			stateTypes.length === 2
		) {
			return HttpResponse.json(counts.failedTaskRuns);
		}
		return HttpResponse.json(counts.totalTaskRuns);
	}),
];

describe("FlowStats", () => {
	it("renders flow stats with all four cards", async () => {
		server.use(
			...createMswHandlers({
				flowRuns: 10,
				totalTaskRuns: 100,
				completedTaskRuns: 80,
				failedTaskRuns: 20,
			}),
		);

		const queryClient = new QueryClient();
		const wrapper = createWrapper({ queryClient });

		render(<FlowStatsRouter flowId={TEST_FLOW_ID} />, { wrapper });

		expect(
			await screen.findByText("Flow Runs (Past Week)"),
		).toBeInTheDocument();
		expect(screen.getByText("Total Task Runs")).toBeInTheDocument();
		expect(screen.getByText("Completed Task Runs")).toBeInTheDocument();
		expect(screen.getByText("Failed Task Runs")).toBeInTheDocument();
	});

	it("displays correct flow runs count", async () => {
		server.use(
			...createMswHandlers({
				flowRuns: 42,
				totalTaskRuns: 100,
				completedTaskRuns: 80,
				failedTaskRuns: 20,
			}),
		);

		const queryClient = new QueryClient();
		const wrapper = createWrapper({ queryClient });

		render(<FlowStatsRouter flowId={TEST_FLOW_ID} />, { wrapper });

		expect(await screen.findByTestId("flow-runs-count")).toHaveTextContent(
			"42",
		);
	});

	it("displays correct task runs counts", async () => {
		server.use(
			...createMswHandlers({
				flowRuns: 10,
				totalTaskRuns: 150,
				completedTaskRuns: 120,
				failedTaskRuns: 30,
			}),
		);

		const queryClient = new QueryClient();
		const wrapper = createWrapper({ queryClient });

		render(<FlowStatsRouter flowId={TEST_FLOW_ID} />, { wrapper });

		expect(await screen.findByTestId("total-task-runs")).toHaveTextContent(
			"150",
		);
		expect(screen.getByTestId("completed-task-runs")).toHaveTextContent("120");
		expect(screen.getByTestId("failed-task-runs")).toHaveTextContent("30");
	});

	it("displays zero counts correctly", async () => {
		server.use(
			...createMswHandlers({
				flowRuns: 0,
				totalTaskRuns: 0,
				completedTaskRuns: 0,
				failedTaskRuns: 0,
			}),
		);

		const queryClient = new QueryClient();
		const wrapper = createWrapper({ queryClient });

		render(<FlowStatsRouter flowId={TEST_FLOW_ID} />, { wrapper });

		expect(await screen.findByTestId("flow-runs-count")).toHaveTextContent("0");
		expect(screen.getByTestId("total-task-runs")).toHaveTextContent("0");
		expect(screen.getByTestId("completed-task-runs")).toHaveTextContent("0");
		expect(screen.getByTestId("failed-task-runs")).toHaveTextContent("0");
	});

	it("renders with different flow ID", async () => {
		const differentFlowId = "different-flow-id";
		server.use(
			...createMswHandlers({
				flowRuns: 5,
				totalTaskRuns: 50,
				completedTaskRuns: 45,
				failedTaskRuns: 5,
			}),
		);

		const queryClient = new QueryClient();
		const wrapper = createWrapper({ queryClient });

		render(<FlowStatsRouter flowId={differentFlowId} />, { wrapper });

		expect(await screen.findByTestId("flow-runs-count")).toHaveTextContent("5");
		expect(screen.getByTestId("total-task-runs")).toHaveTextContent("50");
	});
});
