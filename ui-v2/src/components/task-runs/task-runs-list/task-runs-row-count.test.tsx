import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { createFakeTaskRun } from "@/mocks";
import { TaskRunsRowCount } from "./task-runs-row-count";

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
			mutations: { retry: false },
		},
	});
	const Wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
	return Wrapper;
};

describe("TaskRunsRowCount", () => {
	describe("count-only mode", () => {
		it("should display count with singular label when count is 1", () => {
			render(<TaskRunsRowCount count={1} />);

			expect(screen.getByText("1 Task run")).toBeInTheDocument();
		});

		it("should display count with plural label when count is greater than 1", () => {
			render(<TaskRunsRowCount count={5} />);

			expect(screen.getByText("5 Task runs")).toBeInTheDocument();
		});

		it("should display 0 when count is undefined", () => {
			render(<TaskRunsRowCount count={undefined} />);

			expect(screen.getByText("0 Task runs")).toBeInTheDocument();
		});
	});

	describe("selectable mode", () => {
		it("should display count and checkbox when no rows are selected", () => {
			const taskRuns = [createFakeTaskRun(), createFakeTaskRun()];
			const setSelectedRows = vi.fn();
			const selectedRows = new Set<string>();

			render(
				<TaskRunsRowCount
					count={2}
					results={taskRuns}
					setSelectedRows={setSelectedRows}
					selectedRows={selectedRows}
				/>,
				{ wrapper: createWrapper() },
			);

			expect(screen.getByText("2 Task runs")).toBeInTheDocument();
			expect(screen.getByRole("checkbox")).toBeInTheDocument();
		});

		it("should display selected count when rows are selected", () => {
			const taskRun1 = createFakeTaskRun();
			const taskRun2 = createFakeTaskRun();
			const taskRuns = [taskRun1, taskRun2];
			const setSelectedRows = vi.fn();
			const selectedRows = new Set<string>([taskRun1.id]);

			render(
				<TaskRunsRowCount
					count={2}
					results={taskRuns}
					setSelectedRows={setSelectedRows}
					selectedRows={selectedRows}
				/>,
				{ wrapper: createWrapper() },
			);

			expect(screen.getByText("1 selected")).toBeInTheDocument();
		});

		it("should display delete button when rows are selected", () => {
			const taskRun = createFakeTaskRun();
			const taskRuns = [taskRun];
			const setSelectedRows = vi.fn();
			const selectedRows = new Set<string>([taskRun.id]);

			render(
				<TaskRunsRowCount
					count={1}
					results={taskRuns}
					setSelectedRows={setSelectedRows}
					selectedRows={selectedRows}
				/>,
				{ wrapper: createWrapper() },
			);

			expect(
				screen.getByRole("button", { name: "Delete rows" }),
			).toBeInTheDocument();
		});

		it("should select all rows when checkbox is clicked", async () => {
			const user = userEvent.setup();
			const taskRun1 = createFakeTaskRun();
			const taskRun2 = createFakeTaskRun();
			const taskRuns = [taskRun1, taskRun2];
			const setSelectedRows = vi.fn();
			const selectedRows = new Set<string>();

			render(
				<TaskRunsRowCount
					count={2}
					results={taskRuns}
					setSelectedRows={setSelectedRows}
					selectedRows={selectedRows}
				/>,
				{ wrapper: createWrapper() },
			);

			await user.click(screen.getByRole("checkbox"));

			expect(setSelectedRows).toHaveBeenCalledWith(
				new Set([taskRun1.id, taskRun2.id]),
			);
		});

		it("should deselect all rows when checkbox is clicked and all are selected", async () => {
			const user = userEvent.setup();
			const taskRun1 = createFakeTaskRun();
			const taskRun2 = createFakeTaskRun();
			const taskRuns = [taskRun1, taskRun2];
			const setSelectedRows = vi.fn();
			const selectedRows = new Set<string>([taskRun1.id, taskRun2.id]);

			render(
				<TaskRunsRowCount
					count={2}
					results={taskRuns}
					setSelectedRows={setSelectedRows}
					selectedRows={selectedRows}
				/>,
				{ wrapper: createWrapper() },
			);

			await user.click(screen.getByRole("checkbox"));

			expect(setSelectedRows).toHaveBeenCalledWith(new Set());
		});

		it("should open delete confirmation dialog when delete button is clicked", async () => {
			const user = userEvent.setup();
			const taskRun = createFakeTaskRun();
			const taskRuns = [taskRun];
			const setSelectedRows = vi.fn();
			const selectedRows = new Set<string>([taskRun.id]);

			render(
				<TaskRunsRowCount
					count={1}
					results={taskRuns}
					setSelectedRows={setSelectedRows}
					selectedRows={selectedRows}
				/>,
				{ wrapper: createWrapper() },
			);

			await user.click(screen.getByRole("button", { name: "Delete rows" }));

			expect(screen.getByText("Delete Task Runs")).toBeInTheDocument();
			expect(
				screen.getByText("Are you sure you want to delete selected task runs?"),
			).toBeInTheDocument();
		});
	});
});
