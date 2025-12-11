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
import {
	TaskRunsListItem,
	type TaskRunsListItemData,
} from "./task-runs-list-item";

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

const createMockStateDetails = () => ({
	deferred: false,
	untrackable_result: false,
	pause_reschedule: false,
});

const createMockEmpiricalPolicy = () => ({
	max_retries: 0,
	retry_delay_seconds: 0,
	retries: 0,
	retry_delay: 0,
	retry_jitter_factor: null,
	resuming: null,
});

const createMockTaskRun = (
	overrides: Partial<TaskRunsListItemData> = {},
): TaskRunsListItemData => ({
	id: "task-run-1",
	name: "my-task-run",
	flow_run_id: "flow-run-1",
	task_key: "task-key-1",
	dynamic_key: "0",
	cache_key: null,
	cache_expiration: null,
	task_version: null,
	empirical_policy: createMockEmpiricalPolicy(),
	tags: ["tag1", "tag2"],
	state_id: "state-1",
	task_inputs: {},
	state_type: "COMPLETED",
	state_name: "Completed",
	run_count: 1,
	flow_run_run_count: 1,
	expected_start_time: "2024-01-01T10:00:00Z",
	next_scheduled_start_time: null,
	start_time: "2024-01-01T10:00:00Z",
	end_time: "2024-01-01T10:05:00Z",
	total_run_time: 300,
	estimated_run_time: 300,
	estimated_start_time_delta: 0,
	state: {
		id: "state-1",
		type: "COMPLETED",
		name: "Completed",
		timestamp: "2024-01-01T10:05:00Z",
		message: null,
		state_details: createMockStateDetails(),
		data: null,
	},
	created: "2024-01-01T09:00:00Z",
	updated: "2024-01-01T10:05:00Z",
	...overrides,
});

const createMockFlow = () => ({
	id: "flow-1",
	name: "my-flow",
	created: "2024-01-01T00:00:00Z",
	updated: "2024-01-01T00:00:00Z",
	tags: [],
});

const createMockFlowRun = () => ({
	id: "flow-run-1",
	name: "my-flow-run",
	flow_id: "flow-1",
	deployment_id: null,
	work_queue_name: null,
	work_pool_name: null,
	state_id: "state-1",
	state_type: "COMPLETED" as const,
	state_name: "Completed",
	state: {
		id: "state-1",
		type: "COMPLETED" as const,
		name: "Completed",
		timestamp: "2024-01-01T10:05:00Z",
		message: null,
		state_details: createMockStateDetails(),
		data: null,
	},
	created: "2024-01-01T09:00:00Z",
	updated: "2024-01-01T10:05:00Z",
	tags: [],
	parameters: {},
	idempotency_key: null,
	context: {},
	empirical_policy: createMockEmpiricalPolicy(),
	auto_scheduled: false,
	infrastructure_document_id: null,
	infrastructure_pid: null,
	job_variables: null,
	parent_task_run_id: null,
	run_count: 1,
	expected_start_time: "2024-01-01T10:00:00Z",
	next_scheduled_start_time: null,
	start_time: "2024-01-01T10:00:00Z",
	end_time: "2024-01-01T10:05:00Z",
	total_run_time: 300,
	estimated_run_time: 300,
	estimated_start_time_delta: 0,
});

describe("TaskRunsListItem", () => {
	describe("basic rendering", () => {
		it("renders task run name as a link", async () => {
			const taskRun = createMockTaskRun();
			await renderWithProviders(<TaskRunsListItem taskRun={taskRun} />);

			const link = screen.getByRole("link", { name: "my-task-run" });
			expect(link).toBeVisible();
			expect(link).toHaveAttribute("href", "/runs/task-run/task-run-1");
		});

		it("renders state badge with correct state", async () => {
			const taskRun = createMockTaskRun();
			await renderWithProviders(<TaskRunsListItem taskRun={taskRun} />);

			expect(screen.getByText("Completed")).toBeVisible();
		});

		it("renders tags", async () => {
			const taskRun = createMockTaskRun({ tags: ["tag1", "tag2"] });
			await renderWithProviders(<TaskRunsListItem taskRun={taskRun} />);

			expect(screen.getByText("tag1")).toBeVisible();
			expect(screen.getByText("tag2")).toBeVisible();
		});

		it("renders duration when available", async () => {
			const taskRun = createMockTaskRun({ total_run_time: 300 });
			await renderWithProviders(<TaskRunsListItem taskRun={taskRun} />);

			expect(screen.getByText("5 minutes")).toBeVisible();
		});

		it("does not render duration when zero", async () => {
			const taskRun = createMockTaskRun({
				total_run_time: 0,
				estimated_run_time: 0,
			});
			await renderWithProviders(<TaskRunsListItem taskRun={taskRun} />);

			expect(screen.queryByText("0 seconds")).not.toBeInTheDocument();
		});

		it("renders start time when available", async () => {
			const taskRun = createMockTaskRun({
				start_time: "2024-01-01T10:00:00Z",
			});
			await renderWithProviders(<TaskRunsListItem taskRun={taskRun} />);

			expect(screen.getByText(/2024\/01\/01/)).toBeVisible();
		});

		it("renders expected start time when start_time is not available", async () => {
			const taskRun = createMockTaskRun({
				start_time: null,
				expected_start_time: "2024-01-01T10:00:00Z",
			});
			await renderWithProviders(<TaskRunsListItem taskRun={taskRun} />);

			expect(screen.getByText(/Scheduled for/)).toBeVisible();
		});

		it("renders 'No start time' when neither start_time nor expected_start_time is available", async () => {
			const taskRun = createMockTaskRun({
				start_time: null,
				expected_start_time: null,
			});
			await renderWithProviders(<TaskRunsListItem taskRun={taskRun} />);

			expect(screen.getByText("No start time")).toBeVisible();
		});
	});

	describe("breadcrumb navigation", () => {
		it("renders flow name in breadcrumbs when flow is provided", async () => {
			const taskRun = createMockTaskRun({ flow: createMockFlow() });
			await renderWithProviders(<TaskRunsListItem taskRun={taskRun} />);

			const flowLink = screen.getByRole("link", { name: "my-flow" });
			expect(flowLink).toBeVisible();
			expect(flowLink).toHaveAttribute("href", "/flows/flow/flow-1");
		});

		it("renders flow run name in breadcrumbs when flowRun is provided", async () => {
			const taskRun = createMockTaskRun({ flowRun: createMockFlowRun() });
			await renderWithProviders(<TaskRunsListItem taskRun={taskRun} />);

			const flowRunLink = screen.getByRole("link", { name: "my-flow-run" });
			expect(flowRunLink).toBeVisible();
			expect(flowRunLink).toHaveAttribute("href", "/runs/flow-run/flow-run-1");
		});

		it("renders full breadcrumb path when both flow and flowRun are provided", async () => {
			const taskRun = createMockTaskRun({
				flow: createMockFlow(),
				flowRun: createMockFlowRun(),
			});
			await renderWithProviders(<TaskRunsListItem taskRun={taskRun} />);

			expect(screen.getByRole("link", { name: "my-flow" })).toBeVisible();
			expect(screen.getByRole("link", { name: "my-flow-run" })).toBeVisible();
			expect(screen.getByRole("link", { name: "my-task-run" })).toBeVisible();
		});

		it("renders only task run name when no flow or flowRun is provided", async () => {
			const taskRun = createMockTaskRun();
			await renderWithProviders(<TaskRunsListItem taskRun={taskRun} />);

			expect(screen.getByRole("link", { name: "my-task-run" })).toBeVisible();
			expect(
				screen.queryByRole("link", { name: "my-flow" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("link", { name: "my-flow-run" }),
			).not.toBeInTheDocument();
		});
	});

	describe("checkbox selection", () => {
		it("renders checkbox when checked and onCheckedChange props are provided", async () => {
			const taskRun = createMockTaskRun();
			const onCheckedChange = vi.fn();
			await renderWithProviders(
				<TaskRunsListItem
					taskRun={taskRun}
					checked={false}
					onCheckedChange={onCheckedChange}
				/>,
			);

			expect(screen.getByRole("checkbox")).toBeVisible();
		});

		it("does not render checkbox when checked and onCheckedChange props are not provided", async () => {
			const taskRun = createMockTaskRun();
			await renderWithProviders(<TaskRunsListItem taskRun={taskRun} />);

			expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
		});

		it("calls onCheckedChange when checkbox is clicked", async () => {
			const user = userEvent.setup();
			const taskRun = createMockTaskRun();
			const onCheckedChange = vi.fn();
			await renderWithProviders(
				<TaskRunsListItem
					taskRun={taskRun}
					checked={false}
					onCheckedChange={onCheckedChange}
				/>,
			);

			await user.click(screen.getByRole("checkbox"));
			expect(onCheckedChange).toHaveBeenCalledWith(true);
		});

		it("reflects checked state correctly", async () => {
			const taskRun = createMockTaskRun();
			const onCheckedChange = vi.fn();
			await renderWithProviders(
				<TaskRunsListItem
					taskRun={taskRun}
					checked={true}
					onCheckedChange={onCheckedChange}
				/>,
			);

			expect(screen.getByRole("checkbox")).toBeChecked();
		});
	});

	describe("state-based styling", () => {
		const stateTypes = [
			{ type: "COMPLETED", borderClass: "border-l-green-600" },
			{ type: "FAILED", borderClass: "border-l-red-600" },
			{ type: "RUNNING", borderClass: "border-l-blue-700" },
			{ type: "CANCELLED", borderClass: "border-l-gray-800" },
			{ type: "CANCELLING", borderClass: "border-l-gray-800" },
			{ type: "CRASHED", borderClass: "border-l-orange-600" },
			{ type: "PAUSED", borderClass: "border-l-gray-800" },
			{ type: "PENDING", borderClass: "border-l-gray-800" },
			{ type: "SCHEDULED", borderClass: "border-l-yellow-700" },
		] as const;

		stateTypes.forEach(({ type, borderClass }) => {
			it(`applies ${borderClass} border for ${type} state`, async () => {
				const taskRun = createMockTaskRun({
					state: {
						id: "state-1",
						type,
						name: type,
						timestamp: "2024-01-01T10:00:00Z",
						message: null,
						state_details: createMockStateDetails(),
						data: null,
					},
					state_type: type,
				});
				const { container } = await renderWithProviders(
					<TaskRunsListItem taskRun={taskRun} />,
				);

				const card = container.querySelector('[class*="border-l-"]');
				expect(card).toHaveClass(borderClass);
			});
		});
	});
});
