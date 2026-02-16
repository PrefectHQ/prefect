import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { Suspense } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as flowRunsApi from "@/api/flow-runs";
import type { PaginationState } from "@/components/flow-runs/flow-runs-list/flow-runs-pagination";
import { createFakeWorkPoolQueue } from "@/mocks/create-fake-work-pool-queue";
import { createMockFlow } from "@/mocks/flow";
import { createMockFlowRun } from "@/mocks/flow-run";
import { WorkPoolQueueUpcomingRunsTab } from "./work-pool-queue-upcoming-runs-tab";

const mockFlowRuns = [
	createMockFlowRun({
		id: "run-1",
		name: "Test Run 1",
		flow_id: "flow-1",
		state: { type: "SCHEDULED", name: "Scheduled", id: "state-1" },
	}),
	createMockFlowRun({
		id: "run-2",
		name: "Test Run 2",
		flow_id: "flow-2",
		state: { type: "SCHEDULED", name: "Scheduled", id: "state-2" },
	}),
];

const mockFlows = [
	createMockFlow({ id: "flow-1", name: "Test Flow 1" }),
	createMockFlow({ id: "flow-2", name: "Test Flow 2" }),
];

const mockQueue = createFakeWorkPoolQueue({
	id: "queue-1",
	name: "test-queue",
	work_pool_name: "test-pool",
});

const mockPaginatedResponse = {
	results: mockFlowRuns,
	pages: 1,
	page: 1,
	size: 5,
};

afterEach(() => {
	server.resetHandlers();
});

vi.mock("@/components/flow-runs/flow-runs-list", () => ({
	FlowRunsList: ({ flowRuns }: { flowRuns: Array<{ name?: string }> }) => (
		<div data-testid="flow-runs-list">
			{flowRuns?.map((run, index) => (
				<div key={run.name || index}>{run.name}</div>
			))}
		</div>
	),
}));

vi.mock("@/components/flow-runs/flow-runs-list/flow-runs-pagination", () => ({
	FlowRunsPagination: ({
		count,
		pages,
		pagination,
		onChangePagination,
	}: {
		count: number;
		pages: number;
		pagination: PaginationState;
		onChangePagination: (p: PaginationState) => void;
	}) => (
		<div data-testid="flow-runs-pagination">
			<span>
				Page {pagination.page} of {pages}
			</span>
			<span>Total: {count}</span>
			<button
				type="button"
				onClick={() =>
					onChangePagination({ ...pagination, page: pagination.page + 1 })
				}
				data-testid="next-page"
			>
				Next
			</button>
		</div>
	),
}));

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});
	const Wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>
			<Suspense fallback={<div>Loading...</div>}>{children}</Suspense>
		</QueryClientProvider>
	);
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
};

describe("WorkPoolQueueUpcomingRunsTab", () => {
	const setupMswHandlers = () => {
		server.use(
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json(mockPaginatedResponse);
			}),
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(2);
			}),
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json(mockFlows);
			}),
		);
	};

	it("renders flow runs list with pagination", async () => {
		setupMswHandlers();

		render(
			<WorkPoolQueueUpcomingRunsTab
				workPoolName="test-pool"
				queue={mockQueue}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			expect(screen.getByTestId("flow-runs-list")).toBeInTheDocument();
		});

		await waitFor(() => {
			expect(screen.getByText("Test Run 1")).toBeInTheDocument();
		});
		expect(screen.getByText("Test Run 2")).toBeInTheDocument();
	});

	it("shows pagination controls when multiple pages exist", async () => {
		server.use(
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					...mockPaginatedResponse,
					pages: 3,
				});
			}),
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(15);
			}),
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json(mockFlows);
			}),
		);

		render(
			<WorkPoolQueueUpcomingRunsTab
				workPoolName="test-pool"
				queue={mockQueue}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			expect(screen.getByTestId("flow-runs-pagination")).toBeInTheDocument();
		});

		expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
		expect(screen.getByText("Total: 15")).toBeInTheDocument();
	});

	it("does not show pagination controls for single page", async () => {
		setupMswHandlers();

		render(
			<WorkPoolQueueUpcomingRunsTab
				workPoolName="test-pool"
				queue={mockQueue}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			expect(screen.getByTestId("flow-runs-list")).toBeInTheDocument();
		});

		expect(
			screen.queryByTestId("flow-runs-pagination"),
		).not.toBeInTheDocument();
	});

	it("applies custom className", async () => {
		setupMswHandlers();

		const { container } = render(
			<WorkPoolQueueUpcomingRunsTab
				workPoolName="test-pool"
				queue={mockQueue}
				className="custom-class"
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByTestId("flow-runs-list")).toBeInTheDocument();
		});

		const rootDiv = container.firstElementChild as Element;
		expect(rootDiv).toHaveClass("custom-class");
	});

	it("passes correct pagination filter with work_pool_queues and EXPECTED_START_TIME_ASC sort to API", () => {
		setupMswHandlers();

		const buildPaginateFlowRunsQuery = vi.spyOn(
			flowRunsApi,
			"buildPaginateFlowRunsQuery",
		);

		render(
			<WorkPoolQueueUpcomingRunsTab
				workPoolName="my-work-pool"
				queue={mockQueue}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		expect(buildPaginateFlowRunsQuery).toHaveBeenCalledWith({
			page: 1,
			limit: 5,
			sort: "EXPECTED_START_TIME_ASC",
			work_pools: {
				operator: "and_",
				name: { any_: ["my-work-pool"] },
			},
			work_pool_queues: {
				operator: "and_",
				name: { any_: ["test-queue"] },
			},
			flow_runs: {
				operator: "and_",
				state: {
					operator: "and_",
					name: { any_: ["Scheduled"] },
				},
			},
		});
	});

	it("passes correct count filter with work_pool_queues and default Scheduled state to API", () => {
		setupMswHandlers();

		const buildCountFlowRunsQuery = vi.spyOn(
			flowRunsApi,
			"buildCountFlowRunsQuery",
		);

		render(
			<WorkPoolQueueUpcomingRunsTab
				workPoolName="my-work-pool"
				queue={mockQueue}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		expect(buildCountFlowRunsQuery).toHaveBeenCalledWith({
			work_pools: {
				operator: "and_",
				name: { any_: ["my-work-pool"] },
			},
			work_pool_queues: {
				operator: "and_",
				name: { any_: ["test-queue"] },
			},
			flow_runs: {
				operator: "and_",
				state: {
					operator: "and_",
					name: { any_: ["Scheduled"] },
				},
			},
		});
	});

	it("uses default limit of 5 items", () => {
		setupMswHandlers();

		const buildPaginateFlowRunsQuery = vi.spyOn(
			flowRunsApi,
			"buildPaginateFlowRunsQuery",
		);

		render(
			<WorkPoolQueueUpcomingRunsTab
				workPoolName="test-pool"
				queue={mockQueue}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		expect(buildPaginateFlowRunsQuery).toHaveBeenCalledWith(
			expect.objectContaining({
				limit: 5,
			}),
		);
	});

	it("shows loading state", () => {
		render(
			<WorkPoolQueueUpcomingRunsTab
				workPoolName="test-pool"
				queue={mockQueue}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		expect(screen.getByText("Loading upcoming runs...")).toBeInTheDocument();
	});
});
