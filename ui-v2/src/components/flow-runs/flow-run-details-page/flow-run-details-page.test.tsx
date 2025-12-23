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
});
