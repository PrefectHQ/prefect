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
import type { FlowRun } from "@/api/flow-runs";
import { Toaster } from "@/components/ui/sonner";
import {
	createFakeDeployment,
	createFakeFlow,
	createFakeFlowRun,
	createFakeState,
} from "@/mocks";
import { FlowRunHeader } from "./flow-run-header";

const MOCK_FLOW = createFakeFlow({
	id: "test-flow-id",
	name: "Test Flow Name",
});

const MOCK_DEPLOYMENT = createFakeDeployment({
	id: "test-deployment-id",
	name: "Test Deployment Name",
});

describe("FlowRunHeader", () => {
	const mockFlowRun = createFakeFlowRun({
		id: "test-flow-run-id",
		name: "test-flow-run",
		flow_id: "test-flow-id",
		deployment_id: "test-deployment-id",
		work_pool_name: "test-work-pool",
		state_type: "COMPLETED",
		state_name: "Completed",
		start_time: "2025-05-15T09:45:46Z",
		total_run_time: 7,
		state: createFakeState({
			type: "COMPLETED",
			name: "Completed",
		}),
	});

	const mockOnDeleteClick = vi.fn();

	const renderFlowRunHeader = (
		flowRunOverrides?: Partial<FlowRun>,
		props = {},
	) => {
		const flowRun = flowRunOverrides
			? { ...mockFlowRun, ...flowRunOverrides }
			: mockFlowRun;

		const rootRoute = createRootRoute({
			component: () => (
				<>
					<Toaster />
					<FlowRunHeader
						flowRun={flowRun}
						onDeleteClick={mockOnDeleteClick}
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

		const flowRoute = createRoute({
			path: "/flows/flow/$id",
			getParentRoute: () => rootRoute,
			component: () => <div>Flow Page</div>,
		});

		const deploymentRoute = createRoute({
			path: "/deployments/deployment/$id",
			getParentRoute: () => rootRoute,
			component: () => <div>Deployment Page</div>,
		});

		const routeTree = rootRoute.addChildren([
			runsRoute,
			flowRoute,
			deploymentRoute,
		]);

		const router = createRouter({
			routeTree,
			history: createMemoryHistory({
				initialEntries: ["/"],
			}),
			context: {
				queryClient: new QueryClient(),
			},
		});

		return render(<RouterProvider router={router} />, {
			wrapper: createWrapper(),
		});
	};

	beforeEach(() => {
		vi.clearAllMocks();

		server.use(
			http.get(buildApiUrl("/flows/:id"), () => {
				return HttpResponse.json(MOCK_FLOW);
			}),
			http.get(buildApiUrl("/deployments/:id"), () => {
				return HttpResponse.json(MOCK_DEPLOYMENT);
			}),
			http.post(buildApiUrl("/task_runs/count"), () => {
				return HttpResponse.json(5);
			}),
		);
	});

	it("renders breadcrumb with Runs link and flow run name", async () => {
		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("Runs")).toBeInTheDocument();
		});

		const nav = screen.getByRole("navigation");
		expect(nav).toHaveTextContent("Runs");
		expect(nav).toHaveTextContent("test-flow-run");
	});

	it("renders the Runs breadcrumb link with correct navigation", async () => {
		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("Runs")).toBeInTheDocument();
		});

		const runsLink = screen.getByRole("link", { name: "Runs" });
		expect(runsLink).toHaveAttribute("href", "/runs");
	});

	it("displays the flow run state badge", async () => {
		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("Completed")).toBeInTheDocument();
		});
	});

	it("copies flow run ID to clipboard and shows success toast", async () => {
		renderFlowRunHeader();
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

	it("opens delete confirmation dialog when Delete is clicked", async () => {
		renderFlowRunHeader();
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
	});

	it("calls onDeleteClick when delete is confirmed", async () => {
		renderFlowRunHeader();
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
		});

		await user.click(screen.getByRole("button", { name: /Delete/i }));

		await waitFor(() => {
			expect(mockOnDeleteClick).toHaveBeenCalledTimes(1);
		});
	});

	it("renders with different flow run states", async () => {
		renderFlowRunHeader({
			id: "failed-flow-run-id",
			name: "failed-flow-run",
			state_type: "FAILED",
			state_name: "Failed",
			state: createFakeState({
				type: "FAILED",
				name: "Failed",
			}),
		});

		await waitFor(() => {
			expect(screen.getByText("Failed")).toBeInTheDocument();
		});
	});

	it("displays work pool badge when work_pool_name is present", async () => {
		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("test-work-pool")).toBeInTheDocument();
		});
	});

	it("does not display work pool badge when work_pool_name is not present", async () => {
		renderFlowRunHeader({ work_pool_name: null });

		await waitFor(() => {
			expect(screen.getByText("test-flow-run")).toBeInTheDocument();
		});

		expect(screen.queryByText("test-work-pool")).not.toBeInTheDocument();
	});

	it("displays formatted start time in meta row", async () => {
		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("2025/05/15 09:45:46 AM")).toBeInTheDocument();
		});
	});

	it("displays duration in meta row", async () => {
		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("7s")).toBeInTheDocument();
		});
	});

	it("displays task run count in meta row", async () => {
		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("5 Task runs")).toBeInTheDocument();
		});
	});

	it("displays 'None' when task run count is 0", async () => {
		server.use(
			http.post(buildApiUrl("/task_runs/count"), () => {
				return HttpResponse.json(0);
			}),
		);

		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("None")).toBeInTheDocument();
		});
	});

	it("displays singular 'Task run' when count is 1", async () => {
		server.use(
			http.post(buildApiUrl("/task_runs/count"), () => {
				return HttpResponse.json(1);
			}),
		);

		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("1 Task run")).toBeInTheDocument();
		});
	});

	it("displays flow link with fetched flow name", async () => {
		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("Test Flow Name")).toBeInTheDocument();
		});

		const flowLink = screen.getByRole("link", { name: /FlowTest Flow Name/i });
		expect(flowLink).toHaveAttribute("href", "/flows/flow/test-flow-id");
	});

	it("displays deployment link with fetched deployment name", async () => {
		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("Test Deployment Name")).toBeInTheDocument();
		});

		const deploymentLink = screen.getByRole("link", {
			name: /DeploymentTest Deployment Name/i,
		});
		expect(deploymentLink).toHaveAttribute(
			"href",
			"/deployments/deployment/test-deployment-id",
		);
	});

	it("does not display deployment link when deployment_id is not present", async () => {
		renderFlowRunHeader({ deployment_id: null });

		await waitFor(() => {
			expect(screen.getByText("Test Flow Name")).toBeInTheDocument();
		});

		expect(
			screen.queryByRole("link", { name: /Deployment/i }),
		).not.toBeInTheDocument();
	});

	it("displays loading placeholder while fetching flow name", async () => {
		server.use(
			http.get(buildApiUrl("/flows/:id"), async () => {
				await new Promise((resolve) => setTimeout(resolve, 100));
				return HttpResponse.json(MOCK_FLOW);
			}),
		);

		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("Flow")).toBeInTheDocument();
		});

		const flowLink = screen.getByRole("link", { name: /Flow/i });
		expect(flowLink).toHaveTextContent("...");

		await waitFor(() => {
			expect(screen.getByText("Test Flow Name")).toBeInTheDocument();
		});
	});
});
