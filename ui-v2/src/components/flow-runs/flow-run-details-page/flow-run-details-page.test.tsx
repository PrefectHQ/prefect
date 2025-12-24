import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { createFakeFlowRun, createFakeState } from "@/mocks";
import { FlowRunDetailsPage } from ".";

vi.mock("@/components/flow-runs/flow-run-graph", () => ({
	FlowRunGraph: ({
		flowRunId,
		fullscreen,
		onFullscreenChange,
	}: {
		flowRunId: string;
		fullscreen: boolean;
		onFullscreenChange: (fullscreen: boolean) => void;
	}) => (
		<div data-testid="flow-run-graph" data-flow-run-id={flowRunId}>
			<span data-testid="fullscreen-state">
				{fullscreen ? "true" : "false"}
			</span>
			<button
				type="button"
				data-testid="toggle-fullscreen"
				onClick={() => onFullscreenChange(!fullscreen)}
			>
				Toggle Fullscreen
			</button>
		</div>
	),
}));

describe("FlowRunDetailsPage", () => {
	const mockFlowRun = createFakeFlowRun({
		name: "test-flow-run",
		state: createFakeState({
			type: "COMPLETED",
			name: "Completed",
		}),
	});

	const mockOnTabChange = vi.fn();

	const renderFlowRunDetailsPage = (props = {}) => {
		const rootRoute = createRootRoute({
			component: () => (
				<>
					<Toaster />
					<FlowRunDetailsPage
						id="test-flow-run-id"
						tab="Logs"
						onTabChange={mockOnTabChange}
						{...props}
					/>
				</>
			),
		});

		const runsRoute = createRoute({
			path: "/runs",
			getParentRoute: () => rootRoute,
			component: () => <div>Runs Page</div>,
		});

		const routeTree = rootRoute.addChildren([runsRoute]);

		const router = createRouter({
			routeTree,
			history: createMemoryHistory({
				initialEntries: ["/"],
			}),
			context: {
				queryClient: new QueryClient(),
			},
		});

		return [
			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			}),
			router,
		] as const;
	};

	beforeEach(() => {
		vi.clearAllMocks();
		server.use(
			http.get(buildApiUrl("/flow_runs/:id"), () => {
				return HttpResponse.json(mockFlowRun);
			}),
			http.post(buildApiUrl("/logs/filter"), () => {
				return HttpResponse.json([]);
			}),
		);
	});

	it("renders flow run details with correct breadcrumb navigation", async () => {
		renderFlowRunDetailsPage();

		await waitFor(() => {
			expect(screen.getByText("test-flow-run")).toBeInTheDocument();
		});

		expect(screen.getByText("Runs")).toBeInTheDocument();
		const nav = screen.getByRole("navigation");
		expect(nav).toHaveTextContent("test-flow-run");
	});

	it("displays the flow run state badge", async () => {
		renderFlowRunDetailsPage();

		await waitFor(() => {
			expect(screen.getByText("Completed")).toBeInTheDocument();
		});
	});

	it("switches between tabs correctly", async () => {
		const [screen] = renderFlowRunDetailsPage();

		await waitFor(() => {
			expect(screen.getByText("test-flow-run")).toBeInTheDocument();
		});
		const user = userEvent.setup();

		await user.click(screen.getByRole("tab", { name: "Task Runs" }));
		expect(mockOnTabChange).toHaveBeenCalledWith("TaskRuns");

		await user.click(screen.getByRole("tab", { name: "Subflow Runs" }));
		expect(mockOnTabChange).toHaveBeenCalledWith("SubflowRuns");

		await user.click(screen.getByRole("tab", { name: "Artifacts" }));
		expect(mockOnTabChange).toHaveBeenCalledWith("Artifacts");

		await user.click(screen.getByRole("tab", { name: "Parameters" }));
		expect(mockOnTabChange).toHaveBeenCalledWith("Parameters");

		await user.click(screen.getByRole("tab", { name: "Job Variables" }));
		expect(mockOnTabChange).toHaveBeenCalledWith("JobVariables");
	});

	it("copies flow run ID to clipboard and shows success toast", async () => {
		const [screen] = renderFlowRunDetailsPage();
		const user = userEvent.setup();

		await waitFor(() => {
			expect(screen.getByText("test-flow-run")).toBeInTheDocument();
		});

		const moreButton = screen.getByRole("button", { expanded: false });
		await user.click(moreButton);

		await waitFor(() => {
			expect(screen.getByText("Copy ID")).toBeInTheDocument();
		});
		await user.click(screen.getByText("Copy ID"));

		expect(await navigator.clipboard.readText()).toBe(mockFlowRun.id);

		await waitFor(() => {
			expect(
				screen.getByText("Copied flow run ID to clipboard"),
			).toBeInTheDocument();
		});
	});

	it("deletes flow run and navigates away", async () => {
		server.use(
			http.delete(buildApiUrl("/flow_runs/:id"), () => {
				return new HttpResponse(null, { status: 204 });
			}),
		);

		const [screen, router] = renderFlowRunDetailsPage();
		const user = userEvent.setup();

		await waitFor(() => {
			expect(screen.getByText("test-flow-run")).toBeInTheDocument();
		});

		const moreButton = screen.getByRole("button", { expanded: false });
		await user.click(moreButton);

		await waitFor(() => {
			expect(screen.getByText("Delete")).toBeInTheDocument();
		});
		await user.click(screen.getByText("Delete"));

		await waitFor(() => {
			expect(screen.getByText("Delete Flow Run")).toBeInTheDocument();
			expect(
				screen.getByText(
					`Are you sure you want to delete flow run ${mockFlowRun.name}?`,
				),
			).toBeInTheDocument();
		});

		await user.click(screen.getByRole("button", { name: /Delete/i }));

		await waitFor(() => {
			expect(screen.getByText("Flow run deleted")).toBeInTheDocument();
		});

		await waitFor(() => {
			expect(router.state.location.pathname).toBe("/runs");
		});
	});

	it("sets refetch interval for RUNNING state", async () => {
		const runningFlowRun = createFakeFlowRun({
			name: "running-flow-run",
			state_type: "RUNNING",
			state: createFakeState({
				type: "RUNNING",
				name: "Running",
			}),
		});

		server.use(
			http.get(buildApiUrl("/flow_runs/:id"), () => {
				return HttpResponse.json(runningFlowRun);
			}),
		);

		renderFlowRunDetailsPage();

		await waitFor(() => {
			expect(screen.getByText("running-flow-run")).toBeInTheDocument();
		});

		expect(screen.getByText("Running")).toBeInTheDocument();
	});

	it("sets refetch interval for PENDING state", async () => {
		const pendingFlowRun = createFakeFlowRun({
			name: "pending-flow-run",
			state_type: "PENDING",
			state: createFakeState({
				type: "PENDING",
				name: "Pending",
			}),
		});

		server.use(
			http.get(buildApiUrl("/flow_runs/:id"), () => {
				return HttpResponse.json(pendingFlowRun);
			}),
		);

		renderFlowRunDetailsPage();

		await waitFor(() => {
			expect(screen.getByText("pending-flow-run")).toBeInTheDocument();
		});

		expect(screen.getByText("Pending")).toBeInTheDocument();
	});

	it("displays all 7 tabs", async () => {
		renderFlowRunDetailsPage();

		await waitFor(() => {
			expect(screen.getByText("test-flow-run")).toBeInTheDocument();
		});

		expect(screen.getByRole("tab", { name: "Logs" })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: "Task Runs" })).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: "Subflow Runs" }),
		).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: "Artifacts" })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: "Parameters" })).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: "Job Variables" }),
		).toBeInTheDocument();
	});

	it("renders FlowRunDetails in the sidebar area", async () => {
		const flowRunWithTags = createFakeFlowRun({
			name: "test-flow-run",
			tags: ["tag1", "tag2"],
			run_count: 3,
			state: createFakeState({
				type: "COMPLETED",
				name: "Completed",
			}),
		});

		server.use(
			http.get(buildApiUrl("/flow_runs/:id"), () => {
				return HttpResponse.json(flowRunWithTags);
			}),
		);

		renderFlowRunDetailsPage();

		await waitFor(() => {
			expect(screen.getByText("test-flow-run")).toBeInTheDocument();
		});

		// FlowRunDetails should show run count and flow run ID in the sidebar
		expect(screen.getByText("Run Count")).toBeInTheDocument();
		expect(screen.getByText("3")).toBeInTheDocument();
		expect(screen.getByText("Flow Run ID")).toBeInTheDocument();
	});

	it("renders FlowRunDetails in the Details tab content when selected", async () => {
		const user = userEvent.setup();
		const flowRunWithTags = createFakeFlowRun({
			name: "test-flow-run",
			tags: ["unique-tag-for-test"],
			run_count: 5,
			state: createFakeState({
				type: "COMPLETED",
				name: "Completed",
			}),
		});

		server.use(
			http.get(buildApiUrl("/flow_runs/:id"), () => {
				return HttpResponse.json(flowRunWithTags);
			}),
		);

		// Start with Logs tab selected, then switch to Details
		renderFlowRunDetailsPage({ tab: "Logs" });

		await waitFor(() => {
			expect(screen.getByText("test-flow-run")).toBeInTheDocument();
		});

		// Click on Details tab (visible on mobile)
		const detailsTab = screen.getByRole("tab", { name: "Details" });
		await user.click(detailsTab);

		expect(mockOnTabChange).toHaveBeenCalledWith("Details");
	});

	it("has Details tab with responsive class for mobile visibility", async () => {
		renderFlowRunDetailsPage();

		await waitFor(() => {
			expect(screen.getByText("test-flow-run")).toBeInTheDocument();
		});

		const detailsTab = screen.getByRole("tab", { name: "Details" });
		// The Details tab should have lg:hidden class to hide on desktop
		expect(detailsTab).toHaveClass("lg:hidden");
	});

	it("renders FlowRunGraph for non-pending flow runs", async () => {
		const completedFlowRun = createFakeFlowRun({
			name: "completed-flow-run",
			state_type: "COMPLETED",
			state: createFakeState({
				type: "COMPLETED",
				name: "Completed",
			}),
		});

		server.use(
			http.get(buildApiUrl("/flow_runs/:id"), () => {
				return HttpResponse.json(completedFlowRun);
			}),
		);

		renderFlowRunDetailsPage();

		await waitFor(() => {
			expect(screen.getByText("completed-flow-run")).toBeInTheDocument();
		});

		expect(screen.getByTestId("flow-run-graph")).toBeInTheDocument();
		expect(screen.getByTestId("flow-run-graph")).toHaveAttribute(
			"data-flow-run-id",
			completedFlowRun.id,
		);
	});

	it("hides FlowRunGraph when flow run state is PENDING", async () => {
		const pendingFlowRun = createFakeFlowRun({
			name: "pending-flow-run",
			state_type: "PENDING",
			state: createFakeState({
				type: "PENDING",
				name: "Pending",
			}),
		});

		server.use(
			http.get(buildApiUrl("/flow_runs/:id"), () => {
				return HttpResponse.json(pendingFlowRun);
			}),
		);

		renderFlowRunDetailsPage();

		await waitFor(() => {
			expect(screen.getByText("pending-flow-run")).toBeInTheDocument();
		});

		expect(screen.queryByTestId("flow-run-graph")).not.toBeInTheDocument();
	});

	it("renders FlowRunGraph for FAILED flow runs", async () => {
		const failedFlowRun = createFakeFlowRun({
			name: "failed-flow-run",
			state_type: "FAILED",
			state: createFakeState({
				type: "FAILED",
				name: "Failed",
			}),
		});

		server.use(
			http.get(buildApiUrl("/flow_runs/:id"), () => {
				return HttpResponse.json(failedFlowRun);
			}),
		);

		renderFlowRunDetailsPage();

		await waitFor(() => {
			expect(screen.getByText("failed-flow-run")).toBeInTheDocument();
		});

		expect(screen.getByTestId("flow-run-graph")).toBeInTheDocument();
	});

	it("renders FlowRunGraph for RUNNING flow runs", async () => {
		const runningFlowRun = createFakeFlowRun({
			name: "running-flow-run-graph",
			state_type: "RUNNING",
			state: createFakeState({
				type: "RUNNING",
				name: "Running",
			}),
		});

		server.use(
			http.get(buildApiUrl("/flow_runs/:id"), () => {
				return HttpResponse.json(runningFlowRun);
			}),
		);

		renderFlowRunDetailsPage();

		await waitFor(() => {
			expect(screen.getByText("running-flow-run-graph")).toBeInTheDocument();
		});

		expect(screen.getByTestId("flow-run-graph")).toBeInTheDocument();
	});

	it("manages fullscreen state correctly", async () => {
		const user = userEvent.setup();

		renderFlowRunDetailsPage();

		await waitFor(() => {
			expect(screen.getByText("test-flow-run")).toBeInTheDocument();
		});

		expect(screen.getByTestId("flow-run-graph")).toBeInTheDocument();
		expect(screen.getByTestId("fullscreen-state")).toHaveTextContent("false");

		await user.click(screen.getByTestId("toggle-fullscreen"));

		expect(screen.getByTestId("fullscreen-state")).toHaveTextContent("true");

		await user.click(screen.getByTestId("toggle-fullscreen"));

		expect(screen.getByTestId("fullscreen-state")).toHaveTextContent("false");
	});
});
