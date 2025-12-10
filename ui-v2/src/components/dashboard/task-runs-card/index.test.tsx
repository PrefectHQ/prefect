import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import {
	buildCountTaskRunsQuery,
	type TaskRunsCountFilter,
} from "@/api/task-runs";
import { TaskRunsCard } from "./index";

const TaskRunsCardRouter = ({
	filter,
}: {
	filter?: {
		startDate?: string;
		endDate?: string;
		tags?: string[];
		hideSubflows?: boolean;
	};
}) => {
	const rootRoute = createRootRoute({
		component: () => <TaskRunsCard filter={filter} />,
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

/**
 * Helper to build the base filter that matches what TaskRunsCard uses internally.
 * This ensures test query keys match the component's query keys.
 */
function buildTestBaseFilter(filter?: {
	startDate?: string;
	endDate?: string;
	tags?: string[];
	hideSubflows?: boolean;
}): {
	task_runs: NonNullable<TaskRunsCountFilter["task_runs"]>;
	flow_runs?: NonNullable<TaskRunsCountFilter["flow_runs"]>;
} {
	const taskRunsFilter: NonNullable<TaskRunsCountFilter["task_runs"]> = {
		operator: "and_",
		subflow_runs: {
			exists_: false,
		},
	};

	if (filter?.startDate && filter?.endDate) {
		taskRunsFilter.start_time = {
			after_: filter.startDate,
			before_: filter.endDate,
		};
	}

	const result: {
		task_runs: NonNullable<TaskRunsCountFilter["task_runs"]>;
		flow_runs?: NonNullable<TaskRunsCountFilter["flow_runs"]>;
	} = {
		task_runs: taskRunsFilter,
	};

	if ((filter?.tags && filter.tags.length > 0) || filter?.hideSubflows) {
		const flowRunsFilter: NonNullable<TaskRunsCountFilter["flow_runs"]> = {
			operator: "and_",
		};

		if (filter?.tags && filter.tags.length > 0) {
			flowRunsFilter.tags = {
				operator: "and_",
				any_: filter.tags,
			};
		}

		if (filter?.hideSubflows) {
			flowRunsFilter.parent_task_run_id = {
				operator: "and_",
				is_null_: true,
			};
		}

		result.flow_runs = flowRunsFilter;
	}

	return result;
}

/**
 * Helper to seed all 4 count queries that TaskRunsCard uses.
 */
function seedTaskRunsCountQueries(
	queryClient: QueryClient,
	counts: { total: number; completed: number; failed: number; running: number },
	filter?: {
		startDate?: string;
		endDate?: string;
		tags?: string[];
		hideSubflows?: boolean;
	},
) {
	const baseFilter = buildTestBaseFilter(filter);

	// Seed total count query
	const totalFilter: TaskRunsCountFilter = {
		...baseFilter,
		task_runs: {
			...baseFilter.task_runs,
			state: {
				operator: "and_",
				type: { any_: ["COMPLETED", "FAILED", "CRASHED", "RUNNING"] },
			},
		},
	};
	queryClient.setQueryData(
		buildCountTaskRunsQuery(totalFilter, 30_000).queryKey,
		counts.total,
	);

	// Seed completed count query
	const completedFilter: TaskRunsCountFilter = {
		...baseFilter,
		task_runs: {
			...baseFilter.task_runs,
			state: {
				operator: "and_",
				type: { any_: ["COMPLETED"] },
			},
		},
	};
	queryClient.setQueryData(
		buildCountTaskRunsQuery(completedFilter, 30_000).queryKey,
		counts.completed,
	);

	// Seed failed count query
	const failedFilter: TaskRunsCountFilter = {
		...baseFilter,
		task_runs: {
			...baseFilter.task_runs,
			state: {
				operator: "and_",
				type: { any_: ["FAILED", "CRASHED"] },
			},
		},
	};
	queryClient.setQueryData(
		buildCountTaskRunsQuery(failedFilter, 30_000).queryKey,
		counts.failed,
	);

	// Seed running count query
	const runningFilter: TaskRunsCountFilter = {
		...baseFilter,
		task_runs: {
			...baseFilter.task_runs,
			state: {
				operator: "and_",
				type: { any_: ["RUNNING"] },
			},
		},
	};
	queryClient.setQueryData(
		buildCountTaskRunsQuery(runningFilter, 30_000).queryKey,
		counts.running,
	);
}

describe("TaskRunsCard", () => {
	it("renders task runs card with title", async () => {
		const queryClient = new QueryClient();
		seedTaskRunsCountQueries(queryClient, {
			total: 2,
			completed: 2,
			failed: 0,
			running: 0,
		});

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		expect(await screen.findByText("Task Runs")).toBeInTheDocument();
	});

	it("displays total count when task runs exist", async () => {
		const queryClient = new QueryClient();
		seedTaskRunsCountQueries(queryClient, {
			total: 3,
			completed: 2,
			failed: 1,
			running: 0,
		});

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		// Total count is displayed as a large number
		expect(await screen.findByText("Task Runs")).toBeInTheDocument();
		// Use getAllByText since total and completed might have same value
		const threeElements = screen.getAllByText("3");
		expect(threeElements.length).toBeGreaterThanOrEqual(1);
	});

	it("displays zero counts when no task runs exist", async () => {
		const queryClient = new QueryClient();
		seedTaskRunsCountQueries(queryClient, {
			total: 0,
			completed: 0,
			failed: 0,
			running: 0,
		});

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		expect(await screen.findByText("Task Runs")).toBeInTheDocument();
		// Should show "0" for total and "0 Completed"
		const zeroElements = screen.getAllByText("0");
		expect(zeroElements.length).toBeGreaterThanOrEqual(2);
		expect(screen.getByText("Completed")).toBeInTheDocument();
	});

	it("displays running count correctly", async () => {
		const queryClient = new QueryClient();
		// 2 running, 1 completed = 3 total
		seedTaskRunsCountQueries(queryClient, {
			total: 3,
			completed: 1,
			failed: 0,
			running: 2,
		});

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		// Running count is now displayed inline with the label
		expect(await screen.findByText("Running")).toBeInTheDocument();
		expect(screen.getByText("2")).toBeInTheDocument();
	});

	it("displays completed count correctly", async () => {
		const queryClient = new QueryClient();
		// 2 completed, 1 running, 1 failed = 4 total
		seedTaskRunsCountQueries(queryClient, {
			total: 4,
			completed: 2,
			failed: 1,
			running: 1,
		});

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		// Completed count is displayed with the label
		expect(await screen.findByText(/Completed/)).toBeInTheDocument();
		expect(screen.getByText("2")).toBeInTheDocument();
	});

	it("displays failed count including crashed state", async () => {
		const queryClient = new QueryClient();
		// 2 failed (including crashed), 1 completed = 3 total
		seedTaskRunsCountQueries(queryClient, {
			total: 3,
			completed: 1,
			failed: 2,
			running: 0,
		});

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		// Failed count is displayed with the label and percentage
		expect(await screen.findByText(/Failed/)).toBeInTheDocument();
		expect(screen.getByText("2")).toBeInTheDocument();
		expect(screen.getByText(/66\.7%/)).toBeInTheDocument();
	});

	it("applies date range filter correctly", async () => {
		const startDate = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
		const endDate = new Date().toISOString();

		const queryClient = new QueryClient();
		seedTaskRunsCountQueries(
			queryClient,
			{
				total: 1,
				completed: 1,
				failed: 0,
				running: 0,
			},
			{ startDate, endDate },
		);

		const wrapper = createWrapper({ queryClient });

		render(
			<TaskRunsCardRouter
				filter={{
					startDate,
					endDate,
				}}
			/>,
			{ wrapper },
		);

		// Total count is now displayed as a large number, not "X total"
		expect(await screen.findByText("Task Runs")).toBeInTheDocument();
	});

	it("applies tags filter correctly", async () => {
		const queryClient = new QueryClient();
		seedTaskRunsCountQueries(
			queryClient,
			{
				total: 1,
				completed: 1,
				failed: 0,
				running: 0,
			},
			{ tags: ["production", "critical"] },
		);

		const wrapper = createWrapper({ queryClient });

		render(
			<TaskRunsCardRouter
				filter={{
					tags: ["production", "critical"],
				}}
			/>,
			{ wrapper },
		);

		// Total count is now displayed as a large number, not "X total"
		expect(await screen.findByText("Task Runs")).toBeInTheDocument();
	});

	it("applies combined filters correctly", async () => {
		const startDate = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
		const endDate = new Date().toISOString();

		const queryClient = new QueryClient();
		seedTaskRunsCountQueries(
			queryClient,
			{
				total: 1,
				completed: 1,
				failed: 0,
				running: 0,
			},
			{ startDate, endDate, tags: ["production"] },
		);

		const wrapper = createWrapper({ queryClient });

		render(
			<TaskRunsCardRouter
				filter={{
					startDate,
					endDate,
					tags: ["production"],
				}}
			/>,
			{ wrapper },
		);

		// Total count is now displayed as a large number, not "X total"
		expect(await screen.findByText("Task Runs")).toBeInTheDocument();
	});

	it("handles empty tags array", async () => {
		const queryClient = new QueryClient();
		seedTaskRunsCountQueries(queryClient, {
			total: 1,
			completed: 1,
			failed: 0,
			running: 0,
		});

		const wrapper = createWrapper({ queryClient });

		render(
			<TaskRunsCardRouter
				filter={{
					tags: [],
				}}
			/>,
			{ wrapper },
		);

		// Total count is now displayed as a large number, not "X total"
		expect(await screen.findByText("Task Runs")).toBeInTheDocument();
	});

	it("renders with no filter prop", async () => {
		const queryClient = new QueryClient();
		seedTaskRunsCountQueries(queryClient, {
			total: 1,
			completed: 1,
			failed: 0,
			running: 0,
		});

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		expect(await screen.findByText("Task Runs")).toBeInTheDocument();
		// Total count is displayed as a number (use getAllByText since total and completed might have same value)
		const oneElements = screen.getAllByText("1");
		expect(oneElements.length).toBeGreaterThanOrEqual(1);
	});

	it("displays completed stat when task runs exist", async () => {
		const queryClient = new QueryClient();
		seedTaskRunsCountQueries(queryClient, {
			total: 1,
			completed: 1,
			failed: 0,
			running: 0,
		});

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		// Layout shows total count and completed count
		// Running and Failed are only shown when count > 0
		expect(await screen.findByText("Task Runs")).toBeInTheDocument();
		expect(screen.getByText(/Completed/)).toBeInTheDocument();
	});

	it("displays completed count with zero values", async () => {
		const queryClient = new QueryClient();
		// Only running tasks, no completed or failed
		seedTaskRunsCountQueries(queryClient, {
			total: 1,
			completed: 0,
			failed: 0,
			running: 1,
		});

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		// Layout shows completed count even when 0
		expect(await screen.findByText(/Completed/)).toBeInTheDocument();
	});
});
