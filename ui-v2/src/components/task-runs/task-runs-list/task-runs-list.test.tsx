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
import { createFakeState, createFakeTaskRun } from "@/mocks";
import { TaskRunsList } from "./task-runs-list";

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

describe("TaskRunsList", () => {
	describe("loading state", () => {
		it("renders loading skeletons when taskRuns is undefined", async () => {
			const { container } = await renderWithProviders(
				<TaskRunsList taskRuns={undefined} />,
			);

			const skeletons = container.querySelectorAll('[class*="animate-pulse"]');
			expect(skeletons.length).toBeGreaterThan(0);
		});

		it("renders 5 skeleton items by default", async () => {
			const { container } = await renderWithProviders(
				<TaskRunsList taskRuns={undefined} />,
			);

			const listItems = container.querySelectorAll("li");
			expect(listItems).toHaveLength(5);
		});
	});

	describe("empty state", () => {
		it("renders 'No runs found' message when taskRuns is empty", async () => {
			await renderWithProviders(<TaskRunsList taskRuns={[]} />);

			expect(screen.getByText("No runs found")).toBeVisible();
		});

		it("renders clear filters button when onClearFilters is provided", async () => {
			const onClearFilters = vi.fn();
			await renderWithProviders(
				<TaskRunsList taskRuns={[]} onClearFilters={onClearFilters} />,
			);

			expect(
				screen.getByRole("button", { name: "Clear Filters" }),
			).toBeVisible();
		});

		it("does not render clear filters button when onClearFilters is not provided", async () => {
			await renderWithProviders(<TaskRunsList taskRuns={[]} />);

			expect(
				screen.queryByRole("button", { name: "Clear Filters" }),
			).not.toBeInTheDocument();
		});

		it("calls onClearFilters when clear filters button is clicked", async () => {
			const user = userEvent.setup();
			const onClearFilters = vi.fn();
			await renderWithProviders(
				<TaskRunsList taskRuns={[]} onClearFilters={onClearFilters} />,
			);

			await user.click(screen.getByRole("button", { name: "Clear Filters" }));
			expect(onClearFilters).toHaveBeenCalledTimes(1);
		});
	});

	describe("list rendering", () => {
		it("renders task runs as list items", async () => {
			const taskRuns = [
				createFakeTaskRun({ id: "task-1", name: "Task 1", flow_run_id: null }),
				createFakeTaskRun({ id: "task-2", name: "Task 2", flow_run_id: null }),
				createFakeTaskRun({ id: "task-3", name: "Task 3", flow_run_id: null }),
			];

			await renderWithProviders(<TaskRunsList taskRuns={taskRuns} />);

			expect(screen.getByRole("link", { name: "Task 1" })).toBeVisible();
			expect(screen.getByRole("link", { name: "Task 2" })).toBeVisible();
			expect(screen.getByRole("link", { name: "Task 3" })).toBeVisible();
		});

		it("renders task runs with correct state badges", async () => {
			const taskRuns = [
				createFakeTaskRun({
					id: "task-1",
					name: "Completed Task",
					flow_run_id: null,
					state: createFakeState({ type: "COMPLETED", name: "Completed" }),
					state_type: "COMPLETED",
					state_name: "Completed",
				}),
				createFakeTaskRun({
					id: "task-2",
					name: "Failed Task",
					flow_run_id: null,
					state: createFakeState({ type: "FAILED", name: "Failed" }),
					state_type: "FAILED",
					state_name: "Failed",
				}),
			];

			await renderWithProviders(<TaskRunsList taskRuns={taskRuns} />);

			expect(screen.getByText("Completed")).toBeVisible();
			expect(screen.getByText("Failed")).toBeVisible();
		});
	});

	describe("selectable variant", () => {
		it("renders checkboxes when selection props are provided", async () => {
			const taskRuns = [
				createFakeTaskRun({ id: "task-1", name: "Task 1", flow_run_id: null }),
				createFakeTaskRun({ id: "task-2", name: "Task 2", flow_run_id: null }),
			];
			const selectedRows = new Set<string>();
			const onSelect = vi.fn();

			await renderWithProviders(
				<TaskRunsList
					taskRuns={taskRuns}
					selectedRows={selectedRows}
					onSelect={onSelect}
				/>,
			);

			const checkboxes = screen.getAllByRole("checkbox");
			expect(checkboxes).toHaveLength(2);
		});

		it("does not render checkboxes when selection props are not provided", async () => {
			const taskRuns = [
				createFakeTaskRun({ id: "task-1", name: "Task 1", flow_run_id: null }),
			];

			await renderWithProviders(<TaskRunsList taskRuns={taskRuns} />);

			expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
		});

		it("reflects selected state correctly", async () => {
			const taskRuns = [
				createFakeTaskRun({ id: "task-1", name: "Task 1", flow_run_id: null }),
				createFakeTaskRun({ id: "task-2", name: "Task 2", flow_run_id: null }),
			];
			const selectedRows = new Set(["task-1"]);
			const onSelect = vi.fn();

			await renderWithProviders(
				<TaskRunsList
					taskRuns={taskRuns}
					selectedRows={selectedRows}
					onSelect={onSelect}
				/>,
			);

			const checkboxes = screen.getAllByRole("checkbox");
			expect(checkboxes[0]).toBeChecked();
			expect(checkboxes[1]).not.toBeChecked();
		});

		it("calls onSelect with correct arguments when checkbox is clicked", async () => {
			const user = userEvent.setup();
			const taskRuns = [
				createFakeTaskRun({ id: "task-1", name: "Task 1", flow_run_id: null }),
			];
			const selectedRows = new Set<string>();
			const onSelect = vi.fn();

			await renderWithProviders(
				<TaskRunsList
					taskRuns={taskRuns}
					selectedRows={selectedRows}
					onSelect={onSelect}
				/>,
			);

			await user.click(screen.getByRole("checkbox"));
			expect(onSelect).toHaveBeenCalledWith("task-1", true);
		});

		it("calls onSelect with false when unchecking a selected row", async () => {
			const user = userEvent.setup();
			const taskRuns = [
				createFakeTaskRun({ id: "task-1", name: "Task 1", flow_run_id: null }),
			];
			const selectedRows = new Set(["task-1"]);
			const onSelect = vi.fn();

			await renderWithProviders(
				<TaskRunsList
					taskRuns={taskRuns}
					selectedRows={selectedRows}
					onSelect={onSelect}
				/>,
			);

			await user.click(screen.getByRole("checkbox"));
			expect(onSelect).toHaveBeenCalledWith("task-1", false);
		});
	});
});
