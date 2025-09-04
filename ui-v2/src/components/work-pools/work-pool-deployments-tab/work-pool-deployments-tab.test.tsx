import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { Suspense } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as deploymentsApi from "@/api/deployments";
import * as flowsApi from "@/api/flows";
import { createMockDeployment } from "@/mocks/deployment";
import { createMockFlow } from "@/mocks/flow";
import { WorkPoolDeploymentsTab } from "./work-pool-deployments-tab";

const mockDeployments = [
	createMockDeployment({
		id: "dep-1",
		name: "Deployment 1",
		flow_id: "flow-1",
	}),
	createMockDeployment({
		id: "dep-2",
		name: "Deployment 2",
		flow_id: "flow-2",
	}),
];

const mockFlows = [
	createMockFlow({ id: "flow-1", name: "Flow 1" }),
	createMockFlow({ id: "flow-2", name: "Flow 2" }),
];

// Set up mock handlers for this test
afterEach(() => {
	server.resetHandlers();
});

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
				staleTime: 0,
				gcTime: 0,
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

describe("WorkPoolDeploymentsTab", () => {
	it("renders deployments data table", async () => {
		// Set up handlers for this test
		server.use(
			http.post(buildApiUrl("/deployments/paginate"), () => {
				return HttpResponse.json({
					results: mockDeployments,
					pages: 1,
				});
			}),
			http.post(buildApiUrl("/deployments/count"), () => {
				return HttpResponse.json(2);
			}),
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json(mockFlows);
			}),
		);

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

	it("applies custom className", async () => {
		// Set up handlers for this test
		server.use(
			http.post(buildApiUrl("/deployments/paginate"), () => {
				return HttpResponse.json({
					results: mockDeployments,
					pages: 1,
				});
			}),
			http.post(buildApiUrl("/deployments/count"), () => {
				return HttpResponse.json(2);
			}),
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json(mockFlows);
			}),
		);

		render(
			<WorkPoolDeploymentsTab
				workPoolName="test-pool"
				className="custom-class"
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByTestId("deployments-table")).toBeInTheDocument();
		});

		const parentDiv = screen.getByTestId("deployments-table").parentElement;
		expect(parentDiv).toHaveClass("custom-class");
	});

	it("filters deployments by work pool name", () => {
		const buildPaginateDeploymentsQuerySpy = vi.spyOn(
			deploymentsApi,
			"buildPaginateDeploymentsQuery",
		);

		render(<WorkPoolDeploymentsTab workPoolName="my-work-pool" />, {
			wrapper: createWrapper(),
		});

		expect(buildPaginateDeploymentsQuerySpy).toHaveBeenCalledWith(
			expect.objectContaining({
				work_pools: {
					operator: "and_",
					name: { any_: ["my-work-pool"] },
				},
				deployments: {
					operator: "and_",
					flow_or_deployment_name: { like_: "" },
					tags: { operator: "and_", all_: [] },
				},
			}),
		);
	});

	it("fetches flows for deployments", async () => {
		// Set up handlers for this test
		server.use(
			http.post(buildApiUrl("/deployments/paginate"), () => {
				return HttpResponse.json({
					results: mockDeployments,
					pages: 1,
				});
			}),
			http.post(buildApiUrl("/deployments/count"), () => {
				return HttpResponse.json(2);
			}),
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json(mockFlows);
			}),
		);

		const buildListFlowsQuerySpy = vi.spyOn(flowsApi, "buildListFlowsQuery");

		render(<WorkPoolDeploymentsTab workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(buildListFlowsQuerySpy).toHaveBeenCalledWith(
				expect.objectContaining({
					flows: {
						operator: "and_",
						id: { any_: ["flow-1", "flow-2"] },
					},
					offset: 0,
					sort: "NAME_ASC",
				}),
				expect.objectContaining({
					enabled: true,
				}),
			);
		});
	});
});
