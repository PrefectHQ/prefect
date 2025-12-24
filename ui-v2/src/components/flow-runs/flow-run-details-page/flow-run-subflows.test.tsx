import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	Outlet,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { createContext, type ReactNode, Suspense, useContext } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { createFakeFlow, createFakeFlowRun, createFakeState } from "@/mocks";
import { FlowRunSubflows } from "./flow-run-subflows";

const TestChildrenContext = createContext<ReactNode>(null);

function RenderTestChildren() {
	const children = useContext(TestChildrenContext);
	return (
		<>
			{children}
			<Outlet />
		</>
	);
}

const renderWithProviders = async (ui: ReactNode) => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});

	const rootRoute = createRootRoute({
		component: RenderTestChildren,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
	});

	const result = render(
		<QueryClientProvider client={queryClient}>
			<TestChildrenContext.Provider value={ui}>
				<RouterProvider router={router} />
			</TestChildrenContext.Provider>
		</QueryClientProvider>,
	);

	await waitFor(() => {
		expect(router.state.status).toBe("idle");
	});

	return result;
};

describe("FlowRunSubflows", () => {
	const mockFlows = [
		createFakeFlow({ id: "flow-1", name: "etl-pipeline" }),
		createFakeFlow({ id: "flow-2", name: "data-processor" }),
	];

	const mockSubflowRuns = [
		createFakeFlowRun({
			id: "subflow-1",
			name: "subflow-run-one",
			flow_id: "flow-1",
			state: createFakeState({ type: "COMPLETED", name: "Completed" }),
		}),
		createFakeFlowRun({
			id: "subflow-2",
			name: "subflow-run-two",
			flow_id: "flow-2",
			state: createFakeState({ type: "RUNNING", name: "Running" }),
		}),
		createFakeFlowRun({
			id: "subflow-3",
			name: "subflow-run-three",
			flow_id: "flow-1",
			state: createFakeState({ type: "FAILED", name: "Failed" }),
		}),
	];

	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(3);
			}),
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					results: mockSubflowRuns,
					count: 3,
					pages: 1,
					page: 1,
					limit: 10,
				});
			}),
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json(mockFlows);
			}),
		);
	});

	it("renders subflow runs count", async () => {
		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunSubflows parentFlowRunId="test-parent-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 Subflow runs")).toBeInTheDocument();
		});
	});

	it("renders search input with correct placeholder", async () => {
		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunSubflows parentFlowRunId="test-parent-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 Subflow runs")).toBeInTheDocument();
		});

		const searchInput = screen.getByPlaceholderText("Search by run name");
		expect(searchInput).toBeInTheDocument();
	});

	it("renders state filter dropdown", async () => {
		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunSubflows parentFlowRunId="test-parent-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 Subflow runs")).toBeInTheDocument();
		});

		expect(screen.getByText("All run states")).toBeInTheDocument();
	});

	it("renders sort filter dropdown", async () => {
		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunSubflows parentFlowRunId="test-parent-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 Subflow runs")).toBeInTheDocument();
		});

		expect(screen.getByText("Newest to oldest")).toBeInTheDocument();
	});

	it("renders subflow runs list", async () => {
		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunSubflows parentFlowRunId="test-parent-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 Subflow runs")).toBeInTheDocument();
		});

		await waitFor(() => {
			expect(screen.getByText("subflow-run-one")).toBeInTheDocument();
			expect(screen.getByText("subflow-run-two")).toBeInTheDocument();
			expect(screen.getByText("subflow-run-three")).toBeInTheDocument();
		});
	});

	it("shows empty state when no subflow runs exist", async () => {
		server.use(
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(0);
			}),
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					results: [],
					count: 0,
					pages: 0,
					page: 1,
					limit: 10,
				});
			}),
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json([]);
			}),
		);

		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunSubflows parentFlowRunId="test-parent-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(
				screen.getByText("No subflow runs found for this flow run."),
			).toBeInTheDocument();
		});
	});

	it("renders pagination when there are results", async () => {
		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunSubflows parentFlowRunId="test-parent-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 Subflow runs")).toBeInTheDocument();
		});

		await waitFor(() => {
			expect(screen.getByText("Page 1 of 1")).toBeInTheDocument();
		});
	});

	it("uses correct query parameters for fetching subflows", async () => {
		let requestBody: unknown;
		server.use(
			http.post(buildApiUrl("/flow_runs/paginate"), async ({ request }) => {
				requestBody = await request.json();
				return HttpResponse.json({
					results: mockSubflowRuns,
					count: 3,
					pages: 1,
					page: 1,
					limit: 10,
				});
			}),
		);

		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunSubflows parentFlowRunId="test-parent-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 Subflow runs")).toBeInTheDocument();
		});

		expect(requestBody).toMatchObject({
			flow_runs: {
				operator: "and_",
				parent_flow_run_id: {
					operator: "and_",
					any_: ["test-parent-flow-run-id"],
				},
			},
			sort: "START_TIME_DESC",
			page: 1,
			limit: 10,
		});
	});
});
