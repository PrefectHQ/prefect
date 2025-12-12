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
import { createContext, type ReactNode, useContext } from "react";
import { describe, expect, it, vi } from "vitest";
import { createFakeTaskRun } from "@/mocks";
import { TaskRunsRowCount } from "./task-runs-row-count";

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

describe("TaskRunsRowCount", () => {
	describe("count only variant", () => {
		it("renders count with singular 'Task run' when count is 1", async () => {
			await renderWithProviders(<TaskRunsRowCount count={1} />);

			expect(screen.getByText("1 Task run")).toBeVisible();
		});

		it("renders count with plural 'Task runs' when count is 0", async () => {
			await renderWithProviders(<TaskRunsRowCount count={0} />);

			expect(screen.getByText("0 Task runs")).toBeVisible();
		});

		it("renders count with plural 'Task runs' when count is greater than 1", async () => {
			await renderWithProviders(<TaskRunsRowCount count={5} />);

			expect(screen.getByText("5 Task runs")).toBeVisible();
		});

		it("renders 0 Task runs when count is undefined", async () => {
			await renderWithProviders(<TaskRunsRowCount count={undefined} />);

			expect(screen.getByText("0 Task runs")).toBeVisible();
		});

		it("does not render checkbox when only count is provided", async () => {
			await renderWithProviders(<TaskRunsRowCount count={5} />);

			expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
		});
	});

	describe("selectable variant - no selection", () => {
		it("renders checkbox when selection props are provided", async () => {
			const taskRuns = [
				createFakeTaskRun({ id: "task-1", flow_run_id: null }),
				createFakeTaskRun({ id: "task-2", flow_run_id: null }),
			];

			await renderWithProviders(
				<TaskRunsRowCount
					count={2}
					results={taskRuns}
					selectedRows={new Set<string>()}
					setSelectedRows={vi.fn()}
				/>,
			);

			expect(screen.getByRole("checkbox")).toBeInTheDocument();
		});

		it("renders count text when no rows are selected", async () => {
			const taskRuns = [
				createFakeTaskRun({ id: "task-1", flow_run_id: null }),
				createFakeTaskRun({ id: "task-2", flow_run_id: null }),
			];

			await renderWithProviders(
				<TaskRunsRowCount
					count={2}
					results={taskRuns}
					selectedRows={new Set<string>()}
					setSelectedRows={vi.fn()}
				/>,
			);

			expect(screen.getByText("2 Task runs")).toBeVisible();
		});

		it("checkbox is unchecked when no rows are selected", async () => {
			const taskRuns = [createFakeTaskRun({ id: "task-1", flow_run_id: null })];

			await renderWithProviders(
				<TaskRunsRowCount
					count={1}
					results={taskRuns}
					selectedRows={new Set<string>()}
					setSelectedRows={vi.fn()}
				/>,
			);

			expect(screen.getByRole("checkbox")).not.toBeChecked();
		});

		it("does not render delete button when no rows are selected", async () => {
			const taskRuns = [createFakeTaskRun({ id: "task-1", flow_run_id: null })];

			await renderWithProviders(
				<TaskRunsRowCount
					count={1}
					results={taskRuns}
					selectedRows={new Set<string>()}
					setSelectedRows={vi.fn()}
				/>,
			);

			expect(
				screen.queryByRole("button", { name: "Delete rows" }),
			).not.toBeInTheDocument();
		});

		it("selects all rows when checkbox is clicked", async () => {
			const user = userEvent.setup();
			const taskRuns = [
				createFakeTaskRun({ id: "task-1", flow_run_id: null }),
				createFakeTaskRun({ id: "task-2", flow_run_id: null }),
			];
			const setSelectedRows = vi.fn();

			await renderWithProviders(
				<TaskRunsRowCount
					count={2}
					results={taskRuns}
					selectedRows={new Set<string>()}
					setSelectedRows={setSelectedRows}
				/>,
			);

			await user.click(screen.getByRole("checkbox"));

			expect(setSelectedRows).toHaveBeenCalledWith(
				new Set(["task-1", "task-2"]),
			);
		});
	});

	describe("selectable variant - some rows selected", () => {
		it("renders selected count text", async () => {
			const taskRuns = [
				createFakeTaskRun({ id: "task-1", flow_run_id: null }),
				createFakeTaskRun({ id: "task-2", flow_run_id: null }),
				createFakeTaskRun({ id: "task-3", flow_run_id: null }),
			];

			await renderWithProviders(
				<TaskRunsRowCount
					count={3}
					results={taskRuns}
					selectedRows={new Set(["task-1", "task-2"])}
					setSelectedRows={vi.fn()}
				/>,
			);

			expect(screen.getByText("2 selected")).toBeVisible();
		});

		it("checkbox is in indeterminate state when some rows are selected", async () => {
			const taskRuns = [
				createFakeTaskRun({ id: "task-1", flow_run_id: null }),
				createFakeTaskRun({ id: "task-2", flow_run_id: null }),
			];

			await renderWithProviders(
				<TaskRunsRowCount
					count={2}
					results={taskRuns}
					selectedRows={new Set(["task-1"])}
					setSelectedRows={vi.fn()}
				/>,
			);

			const checkbox = screen.getByRole("checkbox");
			expect(checkbox).toHaveAttribute("data-state", "indeterminate");
		});

		it("renders delete button when rows are selected", async () => {
			const taskRuns = [createFakeTaskRun({ id: "task-1", flow_run_id: null })];

			await renderWithProviders(
				<TaskRunsRowCount
					count={1}
					results={taskRuns}
					selectedRows={new Set(["task-1"])}
					setSelectedRows={vi.fn()}
				/>,
			);

			expect(screen.getByRole("button", { name: "Delete rows" })).toBeVisible();
		});

		it("clears selection when checkbox is clicked while some rows are selected", async () => {
			const user = userEvent.setup();
			const taskRuns = [
				createFakeTaskRun({ id: "task-1", flow_run_id: null }),
				createFakeTaskRun({ id: "task-2", flow_run_id: null }),
			];
			const setSelectedRows = vi.fn();

			await renderWithProviders(
				<TaskRunsRowCount
					count={2}
					results={taskRuns}
					selectedRows={new Set(["task-1"])}
					setSelectedRows={setSelectedRows}
				/>,
			);

			await user.click(screen.getByRole("checkbox"));

			expect(setSelectedRows).toHaveBeenCalledWith(
				new Set(["task-1", "task-2"]),
			);
		});
	});

	describe("selectable variant - all rows selected", () => {
		it("checkbox is checked when all rows are selected", async () => {
			const taskRuns = [
				createFakeTaskRun({ id: "task-1", flow_run_id: null }),
				createFakeTaskRun({ id: "task-2", flow_run_id: null }),
			];

			await renderWithProviders(
				<TaskRunsRowCount
					count={2}
					results={taskRuns}
					selectedRows={new Set(["task-1", "task-2"])}
					setSelectedRows={vi.fn()}
				/>,
			);

			const checkbox = screen.getByRole("checkbox");
			expect(checkbox).toBeChecked();
		});

		it("clears selection when checkbox is clicked while all rows are selected", async () => {
			const user = userEvent.setup();
			const taskRuns = [
				createFakeTaskRun({ id: "task-1", flow_run_id: null }),
				createFakeTaskRun({ id: "task-2", flow_run_id: null }),
			];
			const setSelectedRows = vi.fn();

			await renderWithProviders(
				<TaskRunsRowCount
					count={2}
					results={taskRuns}
					selectedRows={new Set(["task-1", "task-2"])}
					setSelectedRows={setSelectedRows}
				/>,
			);

			await user.click(screen.getByRole("checkbox"));

			expect(setSelectedRows).toHaveBeenCalledWith(new Set());
		});
	});

	describe("delete functionality", () => {
		it("opens delete confirmation dialog when delete button is clicked", async () => {
			const user = userEvent.setup();
			const taskRuns = [createFakeTaskRun({ id: "task-1", flow_run_id: null })];

			await renderWithProviders(
				<TaskRunsRowCount
					count={1}
					results={taskRuns}
					selectedRows={new Set(["task-1"])}
					setSelectedRows={vi.fn()}
				/>,
			);

			await user.click(screen.getByRole("button", { name: "Delete rows" }));

			expect(screen.getByText("Delete Task Runs")).toBeVisible();
			expect(
				screen.getByText("Are you sure you want to delete selected task runs?"),
			).toBeVisible();
		});
	});
});
