import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { Suspense } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as flowRunsApi from "@/api/flow-runs";
import type { PaginationState } from "@/components/flow-runs/flow-runs-list/flow-runs-pagination";
import { createMockFlow } from "@/mocks/flow";
import { createMockFlowRun } from "@/mocks/flow-run";
import { WorkPoolFlowRunsTab } from "./work-pool-flow-runs-tab";

const mockFlowRuns = [
	createMockFlowRun({ id: "run-1", name: "Test Run 1", flow_id: "flow-1" }),
	createMockFlowRun({ id: "run-2", name: "Test Run 2", flow_id: "flow-2" }),
];

const mockFlows = [
	createMockFlow({ id: "flow-1", name: "Test Flow 1" }),
	createMockFlow({ id: "flow-2", name: "Test Flow 2" }),
];

const mockPaginatedResponse = {
	results: mockFlowRuns,
	pages: 1,
	page: 1,
	size: 10,
};

// Set up mock handlers for this test
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

vi.mock(
	"@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filter",
	() => ({
		StateFilter: ({
			onSelectFilter,
		}: {
			onSelectFilter: (filters: Set<string>) => void;
		}) => (
			<div data-testid="state-filter">
				<button
					type="button"
					onClick={() => onSelectFilter(new Set(["Running"]))}
					data-testid="select-running"
				>
					Filter Running
				</button>
			</div>
		),
	}),
);

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

describe("WorkPoolFlowRunsTab", () => {
	const setupMswHandlers = () => {
		server.use(
			// Mock paginate flow runs endpoint
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json(mockPaginatedResponse);
			}),
			// Mock count flow runs endpoint
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(2);
			}),
			// Mock list flows endpoint
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json(mockFlows);
			}),
		);
	};

	it("renders flow runs list with pagination", async () => {
		setupMswHandlers();

		render(<WorkPoolFlowRunsTab workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByTestId("flow-runs-list")).toBeInTheDocument();
		});

		// Check that the flow runs are being rendered by the mocked component
		await waitFor(() => {
			expect(screen.getByText("Test Run 1")).toBeInTheDocument();
		});
		expect(screen.getByText("Test Run 2")).toBeInTheDocument();
	});

	it("renders search input and state filter", async () => {
		setupMswHandlers();

		render(<WorkPoolFlowRunsTab workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(
				screen.getByPlaceholderText("Search flow runs by name..."),
			).toBeInTheDocument();
		});

		expect(screen.getByTestId("state-filter")).toBeInTheDocument();
	});

	it("handles search input changes", async () => {
		setupMswHandlers();
		const user = userEvent.setup();

		render(<WorkPoolFlowRunsTab workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		const searchInput = await screen.findByPlaceholderText(
			"Search flow runs by name...",
		);

		await user.type(searchInput, "test search");

		expect(searchInput).toHaveValue("test search");
	});

	it("handles state filter changes", async () => {
		setupMswHandlers();
		const user = userEvent.setup();

		render(<WorkPoolFlowRunsTab workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByTestId("state-filter")).toBeInTheDocument();
		});

		const filterButton = screen.getByTestId("select-running");
		await user.click(filterButton);

		// Verify state filter interaction works (component should re-render)
		expect(screen.getByTestId("state-filter")).toBeInTheDocument();
	});

	it("shows pagination controls when multiple pages exist", async () => {
		// Set up paginated response with multiple pages
		server.use(
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					...mockPaginatedResponse,
					pages: 3,
				});
			}),
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(150);
			}),
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json(mockFlows);
			}),
		);

		render(<WorkPoolFlowRunsTab workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByTestId("flow-runs-pagination")).toBeInTheDocument();
		});

		expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
		expect(screen.getByText("Total: 150")).toBeInTheDocument();
	});

	it("does not show pagination controls for single page", async () => {
		setupMswHandlers();

		render(<WorkPoolFlowRunsTab workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

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
			<WorkPoolFlowRunsTab workPoolName="test-pool" className="custom-class" />,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByTestId("flow-runs-list")).toBeInTheDocument();
		});

		// The className should be on the root div of the component
		const rootDiv = container.firstElementChild as Element;
		expect(rootDiv).toHaveClass("custom-class");
	});

	it("passes correct pagination filter to API", () => {
		setupMswHandlers();

		const buildPaginateFlowRunsQuery = vi.spyOn(
			flowRunsApi,
			"buildPaginateFlowRunsQuery",
		);

		render(<WorkPoolFlowRunsTab workPoolName="my-work-pool" />, {
			wrapper: createWrapper(),
		});

		expect(buildPaginateFlowRunsQuery).toHaveBeenCalledWith({
			page: 1,
			limit: 10,
			sort: "START_TIME_DESC",
			work_pools: {
				operator: "and_",
				name: { any_: ["my-work-pool"] },
			},
		});
	});

	it("passes correct count filter to API", () => {
		setupMswHandlers();

		const buildCountFlowRunsQuery = vi.spyOn(
			flowRunsApi,
			"buildCountFlowRunsQuery",
		);

		render(<WorkPoolFlowRunsTab workPoolName="my-work-pool" />, {
			wrapper: createWrapper(),
		});

		expect(buildCountFlowRunsQuery).toHaveBeenCalledWith({
			work_pools: {
				operator: "and_",
				name: { any_: ["my-work-pool"] },
			},
		});
	});

	it("shows loading state", () => {
		// Don't set up MSW handlers to simulate loading state
		render(<WorkPoolFlowRunsTab workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Loading flow runs...")).toBeInTheDocument();
	});
});
