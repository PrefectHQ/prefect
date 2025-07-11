import { Toaster } from "@/components/ui/sonner";
import { createFakeState, createFakeTaskRun } from "@/mocks";
import "@/mocks/mock-json-input";
import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TaskRunDetailsPage } from ".";

describe("TaskRunDetailsPage", () => {
	const mockTaskRun = createFakeTaskRun({
		flow_run_name: "test-flow",
		name: "test-task",
		state: createFakeState({
			type: "COMPLETED",
			name: "Completed",
		}),
	});

	const mockOnTabChange = vi.fn();

	const renderTaskRunDetailsPage = (props = {}) => {
		const rootRoute = createRootRoute({
			component: () => (
				<>
					<Toaster />
					<TaskRunDetailsPage
						id="test-task-run-id"
						tab="Logs"
						onTabChange={mockOnTabChange}
						{...props}
					/>
				</>
			),
		});

		// Add a mock route for the flow run page
		const flowRunRoute = createRoute({
			path: "/runs/flow-run/$id",
			getParentRoute: () => rootRoute,
			component: () => <div>Flow Run Page</div>,
		});

		const routeTree = rootRoute.addChildren([flowRunRoute]);

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
		server.use(
			http.get(buildApiUrl("/ui/task_runs/:id"), () => {
				return HttpResponse.json(mockTaskRun);
			}),
		);
	});

	it("renders task run details with correct breadcrumb navigation", async () => {
		renderTaskRunDetailsPage();

		// Wait for the task run data to be loaded
		await waitFor(() => {
			expect(screen.getByText("test-task")).toBeInTheDocument();
		});

		// Check breadcrumb navigation
		expect(screen.getByText("Runs")).toBeInTheDocument();
		const nav = screen.getByRole("navigation");
		expect(nav).toHaveTextContent("test-flow");
		expect(nav).toHaveTextContent("test-task");
	});

	it("displays the task run state badge", async () => {
		renderTaskRunDetailsPage();

		await waitFor(() => {
			expect(screen.getByText("Completed")).toBeInTheDocument();
		});
	});

	it("switches between tabs correctly", async () => {
		const [screen] = renderTaskRunDetailsPage();

		// Wait for the task run data to be loaded
		await waitFor(() => {
			expect(screen.getByText("test-task")).toBeInTheDocument();
		});
		const user = userEvent.setup();

		// Click on different tabs
		await user.click(screen.getByRole("tab", { name: "Artifacts" }));
		expect(mockOnTabChange).toHaveBeenCalledWith("Artifacts");

		await user.click(screen.getByRole("tab", { name: "Task Inputs" }));
		expect(mockOnTabChange).toHaveBeenCalledWith("TaskInputs");

		await user.click(screen.getByRole("tab", { name: "Details" }));
		expect(mockOnTabChange).toHaveBeenCalledWith("Details");
	});

	it("displays the task run inputs", async () => {
		renderTaskRunDetailsPage({ tab: "TaskInputs" });

		await waitFor(() => {
			expect(screen.getByText("test-task")).toBeInTheDocument();
		});

		const tabPanel = screen.getByRole("tabpanel", { name: "Task Inputs" });

		await waitFor(() => {
			expect(within(tabPanel).getByText(/"name": \[\]/)).toBeInTheDocument();
		});
	});

	it("copies task run ID to clipboard and shows success toast", async () => {
		const [screen] = renderTaskRunDetailsPage();
		const user = userEvent.setup();

		// Wait for the task run data to be loaded
		await waitFor(() => {
			expect(screen.getByText("test-task")).toBeInTheDocument();
		});

		// Open the dropdown menu
		const moreButton = screen.getByRole("button", { expanded: false });
		await user.click(moreButton);

		// Wait for the dropdown menu to be visible and click the Copy ID option
		await waitFor(() => {
			expect(screen.getByText("Copy ID")).toBeInTheDocument();
		});
		await user.click(screen.getByText("Copy ID"));

		// Verify clipboard API was called with the correct ID
		expect(await navigator.clipboard.readText()).toBe(mockTaskRun.id);

		// Verify success toast was shown
		await waitFor(() => {
			expect(
				screen.getByText("Copied task run ID to clipboard"),
			).toBeInTheDocument();
		});
	});

	it("deletes task run and navigates away", async () => {
		// Mock the delete API endpoint
		server.use(
			http.delete(buildApiUrl("/task_runs/:id"), () => {
				return new HttpResponse(null, { status: 204 });
			}),
		);

		const [screen, router] = renderTaskRunDetailsPage();
		const user = userEvent.setup();

		// Wait for the task run data to be loaded
		await waitFor(() => {
			expect(screen.getByText("test-task")).toBeInTheDocument();
		});

		// Open the dropdown menu
		const moreButton = screen.getByRole("button", { expanded: false });
		await user.click(moreButton);

		// Wait for the dropdown menu to be visible and click the Delete option
		await waitFor(() => {
			expect(screen.getByText("Delete")).toBeInTheDocument();
		});
		await user.click(screen.getByText("Delete"));

		// Verify delete confirmation dialog appears
		await waitFor(() => {
			expect(screen.getByText("Delete Task Run")).toBeInTheDocument();
			expect(
				screen.getByText(
					`Are you sure you want to delete task run ${mockTaskRun.name}?`,
				),
			).toBeInTheDocument();
		});

		// Click confirm in the dialog
		await user.click(screen.getByRole("button", { name: /Delete/i }));

		// Verify success toast was shown
		await waitFor(() => {
			expect(screen.getByText("Task run deleted")).toBeInTheDocument();
		});

		// Verify we're on the flow run page
		await waitFor(() => {
			expect(router.state.location.pathname).toBe(
				`/runs/flow-run/${mockTaskRun.flow_run_id}`,
			);
		});
	});
});
