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
import { createFakeTaskRun } from "@/mocks";
import { TaskRunCard, type TaskRunCardData } from "./task-run-card";

const TaskRunCardRouter = ({
	taskRun,
	checked,
	onCheckedChange,
}: {
	taskRun: TaskRunCardData;
	checked?: boolean;
	onCheckedChange?: (checked: boolean) => void;
}) => {
	const rootRoute = createRootRoute({
		component: () =>
			checked !== undefined && onCheckedChange ? (
				<TaskRunCard
					taskRun={taskRun}
					checked={checked}
					onCheckedChange={onCheckedChange}
				/>
			) : (
				<TaskRunCard taskRun={taskRun} />
			),
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

describe("TaskRunCard", () => {
	it("should display task run name", async () => {
		const taskRun = createFakeTaskRun({
			name: "test-task-name",
		});
		render(<TaskRunCardRouter taskRun={taskRun} />, {
			wrapper: createWrapper(),
		});

		expect(await screen.findByText("test-task-name")).toBeInTheDocument();
	});

	it("should display state badge", async () => {
		const taskRun = createFakeTaskRun({
			state: {
				type: "COMPLETED",
				name: "Completed",
				id: "test-state-id",
				timestamp: new Date().toISOString(),
			},
		});
		render(<TaskRunCardRouter taskRun={taskRun} />, {
			wrapper: createWrapper(),
		});

		expect(await screen.findByText("Completed")).toBeInTheDocument();
	});

	it("should display tags", async () => {
		const taskRun = createFakeTaskRun({
			tags: ["tag1", "tag2"],
		});
		render(<TaskRunCardRouter taskRun={taskRun} />, {
			wrapper: createWrapper(),
		});

		expect(await screen.findByText("tag1")).toBeInTheDocument();
		expect(screen.getByText("tag2")).toBeInTheDocument();
	});

	it("should display tag count badge when more than 2 tags", async () => {
		const taskRun = createFakeTaskRun({
			tags: ["tag1", "tag2", "tag3"],
		});
		render(<TaskRunCardRouter taskRun={taskRun} />, {
			wrapper: createWrapper(),
		});

		expect(await screen.findByText("3 tags")).toBeInTheDocument();
	});

	it("should display flow run link when flow_run_name is provided", async () => {
		const taskRun = createFakeTaskRun({
			flow_run_name: "test-flow-name",
			flow_run_id: "test-flow-id",
		});
		render(<TaskRunCardRouter taskRun={taskRun} />, {
			wrapper: createWrapper(),
		});

		expect(await screen.findByText("test-flow-name")).toBeInTheDocument();
	});

	it("should not display checkbox when not in selectable mode", async () => {
		const taskRun = createFakeTaskRun({ name: "test-task-no-checkbox" });
		render(<TaskRunCardRouter taskRun={taskRun} />, {
			wrapper: createWrapper(),
		});

		await screen.findByText("test-task-no-checkbox");
		expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
	});

	it("should display checkbox when in selectable mode", async () => {
		const taskRun = createFakeTaskRun();
		const onCheckedChange = vi.fn();
		render(
			<TaskRunCardRouter
				taskRun={taskRun}
				checked={false}
				onCheckedChange={onCheckedChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(await screen.findByRole("checkbox")).toBeInTheDocument();
	});

	it("should call onCheckedChange when checkbox is clicked", async () => {
		const user = userEvent.setup();
		const taskRun = createFakeTaskRun();
		const onCheckedChange = vi.fn();
		render(
			<TaskRunCardRouter
				taskRun={taskRun}
				checked={false}
				onCheckedChange={onCheckedChange}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.click(await screen.findByRole("checkbox"));

		expect(onCheckedChange).toHaveBeenCalledWith(true);
	});

	it("should show checkbox as checked when checked prop is true", async () => {
		const taskRun = createFakeTaskRun();
		const onCheckedChange = vi.fn();
		render(
			<TaskRunCardRouter
				taskRun={taskRun}
				checked={true}
				onCheckedChange={onCheckedChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(await screen.findByRole("checkbox")).toBeChecked();
	});
});
