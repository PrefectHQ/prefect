import { createFakeState, createFakeTaskRun } from "@/mocks";
import { render, screen, waitFor } from "@testing-library/react";
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
		return render(
			<TaskRunDetailsPage
				id="test-task-run-id"
				tab="Logs"
				onTabChange={mockOnTabChange}
				{...props}
			/>,
			{ wrapper: createWrapper() },
		);
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
		expect(screen.getByText("test-flow")).toBeInTheDocument();
		expect(screen.getByText("test-task")).toBeInTheDocument();
	});

	it("displays the task run state badge", async () => {
		renderTaskRunDetailsPage();

		await waitFor(() => {
			expect(screen.getByText("Completed")).toBeInTheDocument();
		});
	});

	it("switches between tabs correctly", async () => {
		renderTaskRunDetailsPage();

		// Click on different tabs
		await userEvent.click(screen.getByRole("tab", { name: "Artifacts" }));
		expect(mockOnTabChange).toHaveBeenCalledWith("Artifacts");

		await userEvent.click(screen.getByRole("tab", { name: "Task Inputs" }));
		expect(mockOnTabChange).toHaveBeenCalledWith("TaskInputs");

		await userEvent.click(screen.getByRole("tab", { name: "Details" }));
		expect(mockOnTabChange).toHaveBeenCalledWith("Details");
	});
});
