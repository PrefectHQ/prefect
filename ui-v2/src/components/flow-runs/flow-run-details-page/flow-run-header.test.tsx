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
import { createWrapper } from "@tests/utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { createFakeFlowRun, createFakeState } from "@/mocks";
import { FlowRunHeader } from "./flow-run-header";

describe("FlowRunHeader", () => {
	const mockFlowRun = createFakeFlowRun({
		id: "test-flow-run-id",
		name: "test-flow-run",
		flow_id: "test-flow-id",
		deployment_id: "test-deployment-id",
		state_type: "COMPLETED",
		state_name: "Completed",
		state: createFakeState({
			type: "COMPLETED",
			name: "Completed",
		}),
	});

	const mockOnDeleteClick = vi.fn();

	const renderFlowRunHeader = (
		flowRun = mockFlowRun,
		onDeleteClick = mockOnDeleteClick,
	) => {
		const rootRoute = createRootRoute({
			component: () => (
				<>
					<Toaster />
					<FlowRunHeader flowRun={flowRun} onDeleteClick={onDeleteClick} />
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
			expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
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
			expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
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
			expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
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
		const failedFlowRun = createFakeFlowRun({
			id: "failed-flow-run-id",
			name: "failed-flow-run",
			state_type: "FAILED",
			state_name: "Failed",
			state: createFakeState({
				type: "FAILED",
				name: "Failed",
			}),
		});

		renderFlowRunHeader(failedFlowRun);

		await waitFor(() => {
			expect(screen.getByText("Failed")).toBeInTheDocument();
		});
	});

	it("renders View Flow link when flow_id exists", async () => {
		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("View Flow")).toBeInTheDocument();
		});

		const flowLink = screen.getByRole("link", { name: "View Flow" });
		expect(flowLink).toHaveAttribute("href", "/flows/flow/test-flow-id");
	});

	it("renders View Deployment link when deployment_id exists", async () => {
		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("View Deployment")).toBeInTheDocument();
		});

		const deploymentLink = screen.getByRole("link", {
			name: "View Deployment",
		});
		expect(deploymentLink).toHaveAttribute(
			"href",
			"/deployments/deployment/test-deployment-id",
		);
	});

	it("does not render View Flow link when flow_id is undefined", async () => {
		const flowRunWithoutFlow = createFakeFlowRun({
			id: "test-flow-run-id",
			name: "test-flow-run",
			flow_id: undefined,
			deployment_id: "test-deployment-id",
			state_type: "COMPLETED",
			state_name: "Completed",
			state: createFakeState({
				type: "COMPLETED",
				name: "Completed",
			}),
		});

		renderFlowRunHeader(flowRunWithoutFlow);

		await waitFor(() => {
			expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
		});

		expect(screen.queryByText("View Flow")).not.toBeInTheDocument();
	});

	it("does not render View Deployment link when deployment_id is null", async () => {
		const flowRunWithoutDeployment = createFakeFlowRun({
			id: "test-flow-run-id",
			name: "test-flow-run",
			flow_id: "test-flow-id",
			deployment_id: null,
			state_type: "COMPLETED",
			state_name: "Completed",
			state: createFakeState({
				type: "COMPLETED",
				name: "Completed",
			}),
		});

		renderFlowRunHeader(flowRunWithoutDeployment);

		await waitFor(() => {
			expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
		});

		expect(screen.queryByText("View Deployment")).not.toBeInTheDocument();
	});

	it("shows Change State menu item in dropdown", async () => {
		renderFlowRunHeader();
		const user = userEvent.setup();

		await waitFor(() => {
			expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
		});

		const moreButton = screen.getByRole("button", { expanded: false });
		await user.click(moreButton);

		await waitFor(() => {
			expect(screen.getByText("Change State")).toBeInTheDocument();
		});
	});

	it("opens state change dialog when Change State is clicked", async () => {
		renderFlowRunHeader();
		const user = userEvent.setup();

		await waitFor(() => {
			expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
		});

		const moreButton = screen.getByRole("button", { expanded: false });
		await user.click(moreButton);

		await waitFor(() => {
			expect(screen.getByText("Change State")).toBeInTheDocument();
		});
		await user.click(screen.getByText("Change State"));

		await waitFor(() => {
			expect(screen.getByText("Change Flow Run State")).toBeInTheDocument();
		});
	});

	it("renders flow run name as h1 in header section", async () => {
		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
				"test-flow-run",
			);
		});
	});
});
