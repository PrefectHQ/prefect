import { createFakeState, createFakeTaskRun } from "@/mocks";
import "@/mocks/mock-json-input";
import { QueryClient } from "@tanstack/react-query";
import {
	RouterProvider,
	createMemoryHistory,
	createRouter,
} from "@tanstack/react-router";
import { createRootRoute } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
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
				<TaskRunDetailsPage
					id="test-task-run-id"
					tab="Logs"
					onTabChange={mockOnTabChange}
					{...props}
				/>
			),
		});
		const router = createRouter({
			routeTree: rootRoute,
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
		const screen = renderTaskRunDetailsPage();

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
});
