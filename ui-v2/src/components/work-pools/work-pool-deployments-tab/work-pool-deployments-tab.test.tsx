import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkPoolDeploymentsTab } from "./work-pool-deployments-tab";
import { createMockDeployment } from "@/mocks/deployment";
import { createMockFlow } from "@/mocks/flow";
import * as deploymentsApi from "@/api/deployments";
import * as flowsApi from "@/api/flows";

const mockDeployments = [
	createMockDeployment({ id: "dep-1", name: "Deployment 1", flow_id: "flow-1" }),
	createMockDeployment({ id: "dep-2", name: "Deployment 2", flow_id: "flow-2" }),
];

const mockFlows = [
	createMockFlow({ id: "flow-1", name: "Flow 1" }),
	createMockFlow({ id: "flow-2", name: "Flow 2" }),
];

vi.mock("@/api/deployments", () => ({
	buildPaginateDeploymentsQuery: vi.fn(() => ({
		queryKey: ["deployments-paginate"],
		queryFn: () => Promise.resolve({
			results: mockDeployments,
			pages: 1,
		}),
	})),
	buildCountDeploymentsQuery: vi.fn(() => ({
		queryKey: ["deployments-count"],
		queryFn: () => Promise.resolve(2),
	})),
}));

vi.mock("@/api/flows", () => ({
	buildListFlowsQuery: vi.fn(() => ({
		queryKey: ["flows-list"],
		queryFn: () => Promise.resolve(mockFlows),
	})),
}));

vi.mock("@/components/deployments/data-table", () => ({
	DeploymentsDataTable: ({
		deployments,
		currentDeploymentsCount,
	}: {
		deployments: Array<{ name: string }>;
		currentDeploymentsCount: number;
	}) => (
		<div data-testid="deployments-table">
			<div>Count: {currentDeploymentsCount}</div>
			{deployments.map((dep) => (
				<div key={dep.name}>{dep.name}</div>
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

describe("WorkPoolDeploymentsTab", () => {
	it("renders deployments data table", async () => {
		render(<WorkPoolDeploymentsTab workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByTestId("deployments-table")).toBeInTheDocument();
		});

		expect(screen.getByText("Count: 2")).toBeInTheDocument();
		expect(screen.getByText("Deployment 1")).toBeInTheDocument();
		expect(screen.getByText("Deployment 2")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const { container } = render(
			<WorkPoolDeploymentsTab workPoolName="test-pool" className="custom-class" />,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toHaveClass("custom-class");
	});

	it("filters deployments by work pool name", () => {
		const buildPaginateDeploymentsQuery = vi.mocked(deploymentsApi.buildPaginateDeploymentsQuery);

		render(<WorkPoolDeploymentsTab workPoolName="my-work-pool" />, {
			wrapper: createWrapper(),
		});

		expect(buildPaginateDeploymentsQuery).toHaveBeenCalledWith(
			expect.objectContaining({
				deployments: {
					operator: "and_",
					work_pool_name: { any_: ["my-work-pool"] },
					flow_or_deployment_name: { like_: "" },
					tags: { operator: "and_", all_: [] },
				},
			}),
		);
	});

	it("fetches flows for deployments", async () => {
		const buildListFlowsQuery = vi.mocked(flowsApi.buildListFlowsQuery);

		render(<WorkPoolDeploymentsTab workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(buildListFlowsQuery).toHaveBeenCalledWith(
				expect.objectContaining({
					flows: {
						operator: "and_",
						id: { any_: ["flow-1", "flow-2"] },
					},
				}),
				expect.anything(),
			);
		});
	});
});