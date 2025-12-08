import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import type { TaskRunCardData } from "@/components/task-runs/task-run-card";
import { createFakeTaskRun } from "@/mocks";
import { TaskRunsList } from "./task-runs-list";

type TaskRunsListRouterProps =
	| {
			taskRuns: Array<TaskRunCardData> | undefined;
			onClearFilters?: () => void;
	  }
	| {
			taskRuns: Array<TaskRunCardData> | undefined;
			onSelect: (id: string, checked: boolean) => void;
			selectedRows: Set<string>;
			onClearFilters?: () => void;
	  };

const TaskRunsListRouter = (props: TaskRunsListRouterProps) => {
	const rootRoute = createRootRoute({
		component: () => <TaskRunsList {...props} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

describe("TaskRunsList", () => {
	it("should display loading skeleton when taskRuns is undefined", async () => {
		render(<TaskRunsListRouter taskRuns={undefined} />, {
			wrapper: createWrapper(),
		});

		await screen.findByRole("list");
		const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
		expect(skeletons.length).toBeGreaterThan(0);
	});

	it("should display empty state when taskRuns is empty array", async () => {
		render(<TaskRunsListRouter taskRuns={[]} />, {
			wrapper: createWrapper(),
		});

		expect(await screen.findByText("No task runs found")).toBeInTheDocument();
	});

	it("should display clear filters button when onClearFilters is provided and taskRuns is empty", async () => {
		const onClearFilters = vi.fn();
		render(
			<TaskRunsListRouter taskRuns={[]} onClearFilters={onClearFilters} />,
			{ wrapper: createWrapper() },
		);

		expect(await screen.findByText("Clear Filters")).toBeInTheDocument();
	});

	it("should call onClearFilters when clear filters button is clicked", async () => {
		const user = userEvent.setup();
		const onClearFilters = vi.fn();
		render(
			<TaskRunsListRouter taskRuns={[]} onClearFilters={onClearFilters} />,
			{ wrapper: createWrapper() },
		);

		await user.click(await screen.findByText("Clear Filters"));

		expect(onClearFilters).toHaveBeenCalled();
	});

	it("should display task runs when taskRuns is provided", async () => {
		const taskRuns = [
			createFakeTaskRun({ name: "task-1" }),
			createFakeTaskRun({ name: "task-2" }),
			createFakeTaskRun({ name: "task-3" }),
		];
		render(<TaskRunsListRouter taskRuns={taskRuns} />, {
			wrapper: createWrapper(),
		});

		expect(await screen.findByText("task-1")).toBeInTheDocument();
		expect(screen.getByText("task-2")).toBeInTheDocument();
		expect(screen.getByText("task-3")).toBeInTheDocument();
	});

	it("should not display checkboxes when not in selectable mode", async () => {
		const taskRuns = [createFakeTaskRun({ name: "task-1" })];
		render(<TaskRunsListRouter taskRuns={taskRuns} />, {
			wrapper: createWrapper(),
		});

		await screen.findByText("task-1");
		expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
	});

	it("should display checkboxes when in selectable mode", async () => {
		const taskRuns = [
			createFakeTaskRun({ name: "task-1" }),
			createFakeTaskRun({ name: "task-2" }),
		];
		const onSelect = vi.fn();
		const selectedRows = new Set<string>();
		render(
			<TaskRunsListRouter
				taskRuns={taskRuns}
				onSelect={onSelect}
				selectedRows={selectedRows}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(await screen.findAllByRole("checkbox")).toHaveLength(2);
	});

	it("should call onSelect when checkbox is clicked", async () => {
		const user = userEvent.setup();
		const taskRun = createFakeTaskRun({ name: "task-1" });
		const taskRuns = [taskRun];
		const onSelect = vi.fn();
		const selectedRows = new Set<string>();
		render(
			<TaskRunsListRouter
				taskRuns={taskRuns}
				onSelect={onSelect}
				selectedRows={selectedRows}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.click(await screen.findByRole("checkbox"));

		expect(onSelect).toHaveBeenCalledWith(taskRun.id, true);
	});

	it("should show checkbox as checked when task run is in selectedRows", async () => {
		const taskRun = createFakeTaskRun({ name: "task-1" });
		const taskRuns = [taskRun];
		const onSelect = vi.fn();
		const selectedRows = new Set<string>([taskRun.id]);
		render(
			<TaskRunsListRouter
				taskRuns={taskRuns}
				onSelect={onSelect}
				selectedRows={selectedRows}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(await screen.findByRole("checkbox")).toBeChecked();
	});
});
