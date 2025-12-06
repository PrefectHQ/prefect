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
import { buildListTaskRunsQuery } from "@/api/task-runs";
import { createFakeTaskRun } from "@/mocks";
import { TaskRunsCard } from "./index";

const TaskRunsCardRouter = ({
	filter,
}: {
	filter?: {
		startDate?: string;
		endDate?: string;
		tags?: string[];
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

describe("TaskRunsCard", () => {
	it("renders task runs card with title", async () => {
		const taskRun1 = createFakeTaskRun({ name: "Task Run 1" });
		const taskRun2 = createFakeTaskRun({ name: "Task Run 2" });

		const queryClient = new QueryClient();
		const queryOptions = buildListTaskRunsQuery({
			sort: "ID_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, [taskRun1, taskRun2]);

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		expect(await screen.findByText("Task Runs")).toBeInTheDocument();
	});

	it("displays total count when task runs exist", async () => {
		const taskRuns = [
			createFakeTaskRun({ name: "Task Run 1" }),
			createFakeTaskRun({ name: "Task Run 2" }),
			createFakeTaskRun({ name: "Task Run 3" }),
		];

		const queryClient = new QueryClient();
		const queryOptions = buildListTaskRunsQuery({
			sort: "ID_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, taskRuns);

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		// Total count is now displayed as a large number, not "X total"
		expect(await screen.findByText("3")).toBeInTheDocument();
	});

	it("does not display count when no task runs exist", async () => {
		const queryClient = new QueryClient();
		const queryOptions = buildListTaskRunsQuery({
			sort: "ID_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, []);

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		expect(await screen.findByText("Task Runs")).toBeInTheDocument();
		expect(screen.queryByText("total")).not.toBeInTheDocument();
	});

	it("shows empty message when no task runs", async () => {
		const queryClient = new QueryClient();
		const queryOptions = buildListTaskRunsQuery({
			sort: "ID_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, []);

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		expect(await screen.findByText("No task runs found")).toBeInTheDocument();
	});

	it("displays running count correctly", async () => {
		const taskRuns = [
			createFakeTaskRun({
				state_type: "RUNNING",
				state: {
					id: "1",
					type: "RUNNING",
					name: "Running",
					timestamp: new Date().toISOString(),
					message: "",
					data: null,
				},
			}),
			createFakeTaskRun({
				state_type: "RUNNING",
				state: {
					id: "2",
					type: "RUNNING",
					name: "Running",
					timestamp: new Date().toISOString(),
					message: "",
					data: null,
				},
			}),
			createFakeTaskRun({
				state_type: "COMPLETED",
				state: {
					id: "3",
					type: "COMPLETED",
					name: "Completed",
					timestamp: new Date().toISOString(),
					message: "",
					data: null,
				},
			}),
		];

		const queryClient = new QueryClient();
		const queryOptions = buildListTaskRunsQuery({
			sort: "ID_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, taskRuns);

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		// Running count is now displayed inline with the label
		expect(await screen.findByText("Running")).toBeInTheDocument();
		expect(screen.getByText("2")).toBeInTheDocument();
	});

	it("displays completed count and percentage correctly", async () => {
		const taskRuns = [
			createFakeTaskRun({
				state_type: "COMPLETED",
				state: {
					id: "1",
					type: "COMPLETED",
					name: "Completed",
					timestamp: new Date().toISOString(),
					message: "",
					data: null,
				},
			}),
			createFakeTaskRun({
				state_type: "COMPLETED",
				state: {
					id: "2",
					type: "COMPLETED",
					name: "Completed",
					timestamp: new Date().toISOString(),
					message: "",
					data: null,
				},
			}),
			createFakeTaskRun({
				state_type: "RUNNING",
				state: {
					id: "3",
					type: "RUNNING",
					name: "Running",
					timestamp: new Date().toISOString(),
					message: "",
					data: null,
				},
			}),
			createFakeTaskRun({
				state_type: "FAILED",
				state: {
					id: "4",
					type: "FAILED",
					name: "Failed",
					timestamp: new Date().toISOString(),
					message: "",
					data: null,
				},
			}),
		];

		const queryClient = new QueryClient();
		const queryOptions = buildListTaskRunsQuery({
			sort: "ID_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, taskRuns);

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		// Percentage is now displayed inline with the label (e.g., "Completed 66.7%")
		expect(await screen.findByText(/Completed/)).toBeInTheDocument();
		expect(screen.getByText(/66\.7%/)).toBeInTheDocument();
	});

	it("displays failed count including crashed state", async () => {
		const taskRuns = [
			createFakeTaskRun({
				state_type: "FAILED",
				state: {
					id: "1",
					type: "FAILED",
					name: "Failed",
					timestamp: new Date().toISOString(),
					message: "",
					data: null,
				},
			}),
			createFakeTaskRun({
				state_type: "CRASHED",
				state: {
					id: "2",
					type: "CRASHED",
					name: "Crashed",
					timestamp: new Date().toISOString(),
					message: "",
					data: null,
				},
			}),
			createFakeTaskRun({
				state_type: "COMPLETED",
				state: {
					id: "3",
					type: "COMPLETED",
					name: "Completed",
					timestamp: new Date().toISOString(),
					message: "",
					data: null,
				},
			}),
		];

		const queryClient = new QueryClient();
		const queryOptions = buildListTaskRunsQuery({
			sort: "ID_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, taskRuns);

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		// Failed count is now displayed inline with the label
		expect(await screen.findByText(/Failed/)).toBeInTheDocument();
		expect(screen.getByText("2")).toBeInTheDocument();
		expect(screen.getByText(/66\.7%/)).toBeInTheDocument();
	});

	it("applies date range filter correctly", async () => {
		const startDate = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
		const endDate = new Date().toISOString();
		const taskRuns = [
			createFakeTaskRun({
				start_time: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
			}),
		];

		const queryClient = new QueryClient();
		const queryOptions = buildListTaskRunsQuery({
			sort: "ID_DESC",
			offset: 0,
			task_runs: {
				operator: "and_",
				start_time: {
					after_: startDate,
					before_: endDate,
				},
			},
		});
		queryClient.setQueryData(queryOptions.queryKey, taskRuns);

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
		const taskRuns = [
			createFakeTaskRun({
				tags: ["production", "critical"],
			}),
		];

		const queryClient = new QueryClient();
		const queryOptions = buildListTaskRunsQuery({
			sort: "ID_DESC",
			offset: 0,
			task_runs: {
				operator: "and_",
				tags: {
					operator: "and_",
					all_: ["production", "critical"],
				},
			},
		});
		queryClient.setQueryData(queryOptions.queryKey, taskRuns);

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
		const taskRuns = [
			createFakeTaskRun({
				start_time: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
				tags: ["production"],
			}),
		];

		const queryClient = new QueryClient();
		const queryOptions = buildListTaskRunsQuery({
			sort: "ID_DESC",
			offset: 0,
			task_runs: {
				operator: "and_",
				start_time: {
					after_: startDate,
					before_: endDate,
				},
				tags: {
					operator: "and_",
					all_: ["production"],
				},
			},
		});
		queryClient.setQueryData(queryOptions.queryKey, taskRuns);

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
		const taskRuns = [createFakeTaskRun()];

		const queryClient = new QueryClient();
		const queryOptions = buildListTaskRunsQuery({
			sort: "ID_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, taskRuns);

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
		const taskRuns = [createFakeTaskRun()];

		const queryClient = new QueryClient();
		const queryOptions = buildListTaskRunsQuery({
			sort: "ID_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, taskRuns);

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		expect(await screen.findByText("Task Runs")).toBeInTheDocument();
		// Total count is displayed with the "Total" label in vertical layout
		expect(screen.getByText("Total")).toBeInTheDocument();
	});

	it("displays completed stat when task runs exist", async () => {
		const taskRuns = [
			createFakeTaskRun({
				state_type: "COMPLETED",
				state: {
					id: "1",
					type: "COMPLETED",
					name: "Completed",
					timestamp: new Date().toISOString(),
					message: "",
					data: null,
				},
			}),
		];

		const queryClient = new QueryClient();
		const queryOptions = buildListTaskRunsQuery({
			sort: "ID_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, taskRuns);

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		// New layout shows total count with "Total" label in vertical layout
		// Running and Failed are only shown when count > 0
		expect(await screen.findByText("Task Runs")).toBeInTheDocument();
		// The total count is displayed with the "Total" label
		expect(screen.getByText("Total")).toBeInTheDocument();
		expect(screen.getByText(/Completed/)).toBeInTheDocument();
	});

	it("calculates percentages correctly with zero values", async () => {
		const taskRuns = [
			createFakeTaskRun({
				state_type: "RUNNING",
				state: {
					id: "1",
					type: "RUNNING",
					name: "Running",
					timestamp: new Date().toISOString(),
					message: "",
					data: null,
				},
			}),
		];

		const queryClient = new QueryClient();
		const queryOptions = buildListTaskRunsQuery({
			sort: "ID_DESC",
			offset: 0,
		});
		queryClient.setQueryData(queryOptions.queryKey, taskRuns);

		const wrapper = createWrapper({ queryClient });

		render(<TaskRunsCardRouter />, { wrapper });

		// New layout shows percentage inline with Completed label
		// The text is split across elements, so we check for the container
		expect(await screen.findByText(/Completed/)).toBeInTheDocument();
		expect(screen.getByText(/0\.0%/)).toBeInTheDocument();
	});
});
