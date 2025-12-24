import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	Outlet,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { createContext, type ReactNode, Suspense, useContext } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { createFakeState, createFakeTaskRunResponse } from "@/mocks";
import { FlowRunTaskRuns } from "./flow-run-task-runs";

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

describe("FlowRunTaskRuns", () => {
	const mockTaskRuns = [
		createFakeTaskRunResponse({
			id: "task-1",
			name: "task_one-abc",
			state: createFakeState({ type: "COMPLETED", name: "Completed" }),
			tags: ["tag1"],
		}),
		createFakeTaskRunResponse({
			id: "task-2",
			name: "task_two-def",
			state: createFakeState({ type: "COMPLETED", name: "Completed" }),
			tags: ["tag2"],
		}),
		createFakeTaskRunResponse({
			id: "task-3",
			name: "task_three-ghi",
			state: createFakeState({ type: "FAILED", name: "Failed" }),
			tags: [],
		}),
	];

	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/task_runs/count"), () => {
				return HttpResponse.json(3);
			}),
			http.post(buildApiUrl("/task_runs/paginate"), () => {
				return HttpResponse.json({
					results: mockTaskRuns,
					count: 3,
					pages: 1,
					page: 1,
					limit: 20,
				});
			}),
		);
	});

	it("renders task runs count and state summary", async () => {
		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunTaskRuns flowRunId="test-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 Task runs")).toBeInTheDocument();
		});

		// Check state summary is displayed
		await waitFor(() => {
			expect(screen.getByText(/2 Completed/)).toBeInTheDocument();
		});
	});

	it("renders search input with correct placeholder", async () => {
		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunTaskRuns flowRunId="test-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 Task runs")).toBeInTheDocument();
		});

		const searchInput = screen.getByPlaceholderText("Search by run name");
		expect(searchInput).toBeInTheDocument();
	});

	it("renders state filter dropdown", async () => {
		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunTaskRuns flowRunId="test-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 Task runs")).toBeInTheDocument();
		});

		expect(screen.getByText("All run states")).toBeInTheDocument();
	});

	it("renders tags filter input", async () => {
		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunTaskRuns flowRunId="test-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 Task runs")).toBeInTheDocument();
		});

		const tagsInput = screen.getByPlaceholderText("All tags");
		expect(tagsInput).toBeInTheDocument();
	});

	it("renders sort filter dropdown", async () => {
		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunTaskRuns flowRunId="test-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 Task runs")).toBeInTheDocument();
		});

		expect(screen.getByText("Newest to oldest")).toBeInTheDocument();
	});

	it("renders task runs list", async () => {
		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunTaskRuns flowRunId="test-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 Task runs")).toBeInTheDocument();
		});

		// Check that task runs are rendered
		await waitFor(() => {
			expect(screen.getByText("task_one-abc")).toBeInTheDocument();
			expect(screen.getByText("task_two-def")).toBeInTheDocument();
			expect(screen.getByText("task_three-ghi")).toBeInTheDocument();
		});
	});

	it("shows empty state when no task runs exist", async () => {
		server.use(
			http.post(buildApiUrl("/task_runs/count"), () => {
				return HttpResponse.json(0);
			}),
			http.post(buildApiUrl("/task_runs/paginate"), () => {
				return HttpResponse.json({
					results: [],
					count: 0,
					pages: 0,
					page: 1,
					limit: 20,
				});
			}),
		);

		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunTaskRuns flowRunId="test-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(
				screen.getByText("No task runs found for this flow run."),
			).toBeInTheDocument();
		});
	});

	it("allows typing in search input", async () => {
		const user = userEvent.setup();

		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunTaskRuns flowRunId="test-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 Task runs")).toBeInTheDocument();
		});

		const searchInput = screen.getByPlaceholderText("Search by run name");
		await user.type(searchInput, "task_one");

		expect(searchInput).toHaveValue("task_one");
	});

	it("renders pagination when there are results", async () => {
		await renderWithProviders(
			<Suspense fallback={<div>Loading...</div>}>
				<FlowRunTaskRuns flowRunId="test-flow-run-id" />
			</Suspense>,
		);

		await waitFor(() => {
			expect(screen.getByText("3 Task runs")).toBeInTheDocument();
		});

		// Wait for task runs to load and pagination to appear
		await waitFor(() => {
			expect(screen.getByText("Page 1 of 1")).toBeInTheDocument();
		});
	});
});
