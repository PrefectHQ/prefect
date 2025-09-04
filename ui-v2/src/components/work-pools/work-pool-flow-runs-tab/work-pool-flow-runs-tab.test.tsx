import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { Suspense } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as flowRunsApi from "@/api/flow-runs";
import { createMockFlowRun } from "@/mocks/flow-run";
import { WorkPoolFlowRunsTab } from "./work-pool-flow-runs-tab";

const mockFlowRuns = [
	createMockFlowRun({ id: "run-1", name: "Test Run 1" }),
	createMockFlowRun({ id: "run-2", name: "Test Run 2" }),
];

// Set up mock handlers for this test
afterEach(() => {
	server.resetHandlers();
});

vi.mock("@/components/flow-runs/flow-runs-list", () => ({
	FlowRunsList: ({ flowRuns }: { flowRuns: Array<{ name: string }> }) => (
		<div data-testid="flow-runs-list">
			{flowRuns?.map((run) => (
				<div key={run.name}>{run.name}</div>
			))}
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

describe("WorkPoolFlowRunsTab", () => {
	it("renders flow runs list", async () => {
		// Set up MSW handler for this test
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json(mockFlowRuns);
			}),
		);

		render(<WorkPoolFlowRunsTab workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByTestId("flow-runs-list")).toBeInTheDocument();
		});

		expect(screen.getByText("Test Run 1")).toBeInTheDocument();
		expect(screen.getByText("Test Run 2")).toBeInTheDocument();
	});

	it("applies custom className", async () => {
		// Set up MSW handler for this test
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json(mockFlowRuns);
			}),
		);

		render(
			<WorkPoolFlowRunsTab workPoolName="test-pool" className="custom-class" />,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByTestId("flow-runs-list")).toBeInTheDocument();
		});

		const parentDiv = screen.getByTestId("flow-runs-list").parentElement;
		expect(parentDiv).toHaveClass("custom-class");
	});

	it("passes correct filter to API", () => {
		// Set up MSW handler for this test
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json(mockFlowRuns);
			}),
		);

		const buildFilterFlowRunsQuery = vi.spyOn(
			flowRunsApi,
			"buildFilterFlowRunsQuery",
		);

		render(<WorkPoolFlowRunsTab workPoolName="my-work-pool" />, {
			wrapper: createWrapper(),
		});

		expect(buildFilterFlowRunsQuery).toHaveBeenCalledWith({
			work_pools: {
				operator: "and_",
				name: { any_: ["my-work-pool"] },
			},
			limit: 50,
			offset: 0,
			sort: "START_TIME_DESC",
		});
	});
});
