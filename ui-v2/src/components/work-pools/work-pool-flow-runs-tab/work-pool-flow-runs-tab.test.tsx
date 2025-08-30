import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkPoolFlowRunsTab } from "./work-pool-flow-runs-tab";
import { createMockFlowRun } from "@/mocks/flow-run";
import * as flowRunsApi from "@/api/flow-runs";

const mockFlowRuns = [
	createMockFlowRun({ id: "run-1", name: "Test Run 1" }),
	createMockFlowRun({ id: "run-2", name: "Test Run 2" }),
];

vi.mock("@/api/flow-runs", () => ({
	buildFilterFlowRunsQuery: vi.fn(() => ({
		queryKey: ["test-key"],
		queryFn: () => Promise.resolve(mockFlowRuns),
	})),
}));

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
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
};

describe("WorkPoolFlowRunsTab", () => {
	it("renders flow runs list", async () => {
		render(<WorkPoolFlowRunsTab workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByTestId("flow-runs-list")).toBeInTheDocument();
		});
		
		expect(screen.getByText("Test Run 1")).toBeInTheDocument();
		expect(screen.getByText("Test Run 2")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const { container } = render(
			<WorkPoolFlowRunsTab workPoolName="test-pool" className="custom-class" />,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toHaveClass("custom-class");
	});

	it("passes correct filter to API", () => {
		const buildFilterFlowRunsQuery = vi.mocked(flowRunsApi.buildFilterFlowRunsQuery);

		render(<WorkPoolFlowRunsTab workPoolName="my-work-pool" />, {
			wrapper: createWrapper(),
		});

		expect(buildFilterFlowRunsQuery).toHaveBeenCalledWith({
			work_pools: { 
				operator: "and_",
				name: { any_: ["my-work-pool"] },
			},
			limit: 100,
			offset: 0,
			sort: "START_TIME_DESC",
		});
	});
});