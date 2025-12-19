import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { createFakeFlowRunWithFlow } from "@/mocks/create-fake-flow-run";
import { createFakeWorkPoolQueue } from "@/mocks/create-fake-work-pool-queue";
import { createMockFlow } from "@/mocks/flow";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { WorkPoolQueueUpcomingRunsTab } from "./work-pool-queue-upcoming-runs-tab";

const mockQueue = createFakeWorkPoolQueue({
	id: "queue-1",
	name: "default",
	work_pool_name: "my-work-pool",
	status: "READY",
	is_paused: false,
});

const mockPausedQueue = createFakeWorkPoolQueue({
	id: "queue-2",
	name: "paused-queue",
	work_pool_name: "my-work-pool",
	status: "PAUSED",
	is_paused: true,
});

const mockFlows = [
	createMockFlow({ id: "flow-1", name: "ETL Pipeline" }),
	createMockFlow({ id: "flow-2", name: "Data Sync" }),
	createMockFlow({ id: "flow-3", name: "Report Generator" }),
];

const mockScheduledFlowRuns = [
	createFakeFlowRunWithFlow({
		id: "run-1",
		name: "etl-pipeline-scheduled-1",
		flow_id: "flow-1",
		state: { type: "SCHEDULED", name: "Scheduled", id: "state-1" },
	}),
	createFakeFlowRunWithFlow({
		id: "run-2",
		name: "data-sync-scheduled-1",
		flow_id: "flow-2",
		state: { type: "SCHEDULED", name: "Scheduled", id: "state-2" },
	}),
	createFakeFlowRunWithFlow({
		id: "run-3",
		name: "report-generator-scheduled-1",
		flow_id: "flow-3",
		state: { type: "SCHEDULED", name: "Scheduled", id: "state-3" },
	}),
	createFakeFlowRunWithFlow({
		id: "run-4",
		name: "etl-pipeline-scheduled-2",
		flow_id: "flow-1",
		state: { type: "SCHEDULED", name: "Scheduled", id: "state-4" },
	}),
	createFakeFlowRunWithFlow({
		id: "run-5",
		name: "data-sync-scheduled-2",
		flow_id: "flow-2",
		state: { type: "SCHEDULED", name: "Scheduled", id: "state-5" },
	}),
];

const meta = {
	title: "Components/WorkPools/WorkPoolQueueUpcomingRunsTab",
	component: WorkPoolQueueUpcomingRunsTab,
	decorators: [routerDecorator, reactQueryDecorator, toastDecorator],
	parameters: {
		layout: "padded",
	},
	args: {
		workPoolName: "my-work-pool",
		queue: mockQueue,
	},
	argTypes: {
		workPoolName: {
			control: "text",
			description: "Name of the work pool",
		},
		queue: {
			control: "object",
			description: "Work pool queue object",
		},
		className: {
			control: "text",
			description: "Additional CSS classes to apply",
		},
	},
	tags: ["autodocs"],
} satisfies Meta<typeof WorkPoolQueueUpcomingRunsTab>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/paginate"), () => {
					return HttpResponse.json({
						results: mockScheduledFlowRuns,
						pages: 1,
						page: 1,
						size: 5,
					});
				}),
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(5);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json(mockFlows);
				}),
				http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
					return HttpResponse.json({
						"run-1": 0,
						"run-2": 0,
						"run-3": 0,
						"run-4": 0,
						"run-5": 0,
					});
				}),
			],
		},
	},
};

export const Empty: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/paginate"), () => {
					return HttpResponse.json({
						results: [],
						pages: 0,
						page: 1,
						size: 5,
					});
				}),
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(0);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json([]);
				}),
				http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
					return HttpResponse.json({});
				}),
			],
		},
	},
};

export const QueuePaused: Story = {
	args: {
		queue: mockPausedQueue,
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/paginate"), () => {
					return HttpResponse.json({
						results: [],
						pages: 0,
						page: 1,
						size: 5,
					});
				}),
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(0);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json([]);
				}),
				http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
					return HttpResponse.json({});
				}),
			],
		},
	},
};

export const Loading: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/paginate"), async () => {
					await new Promise((resolve) => setTimeout(resolve, 100000));
					return HttpResponse.json({
						results: [],
						pages: 0,
						page: 1,
						size: 5,
					});
				}),
				http.post(buildApiUrl("/flow_runs/count"), async () => {
					await new Promise((resolve) => setTimeout(resolve, 100000));
					return HttpResponse.json(0);
				}),
				http.post(buildApiUrl("/flows/filter"), async () => {
					await new Promise((resolve) => setTimeout(resolve, 100000));
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const WithPagination: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/paginate"), () => {
					return HttpResponse.json({
						results: mockScheduledFlowRuns,
						pages: 5,
						page: 1,
						size: 5,
					});
				}),
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(25);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json(mockFlows);
				}),
				http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
					return HttpResponse.json({
						"run-1": 0,
						"run-2": 0,
						"run-3": 0,
						"run-4": 0,
						"run-5": 0,
					});
				}),
			],
		},
	},
};
