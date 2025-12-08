import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { Suspense } from "react";
import { createFakeFlow, createFakeFlowRun } from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunsAccordion } from "./index";

const MOCK_FLOWS = [
	createFakeFlow({ id: "flow-1", name: "ETL Pipeline" }),
	createFakeFlow({ id: "flow-2", name: "Data Sync" }),
	createFakeFlow({ id: "flow-3", name: "Report Generator" }),
];

const now = new Date();

const MOCK_FAILED_FLOW_RUNS = [
	createFakeFlowRun({
		id: "run-1",
		name: "failed-run-1",
		flow_id: "flow-1",
		state_type: "FAILED",
		state_name: "Failed",
		start_time: new Date(now.getTime() - 30 * 60 * 1000).toISOString(),
		estimated_run_time: 120,
	}),
	createFakeFlowRun({
		id: "run-2",
		name: "failed-run-2",
		flow_id: "flow-1",
		state_type: "FAILED",
		state_name: "Failed",
		start_time: new Date(now.getTime() - 60 * 60 * 1000).toISOString(),
		estimated_run_time: 300,
	}),
	createFakeFlowRun({
		id: "run-3",
		name: "crashed-run-1",
		flow_id: "flow-2",
		state_type: "CRASHED",
		state_name: "Crashed",
		start_time: new Date(now.getTime() - 45 * 60 * 1000).toISOString(),
		estimated_run_time: 180,
	}),
];

const MOCK_RUNNING_FLOW_RUNS = [
	createFakeFlowRun({
		id: "run-4",
		name: "running-run-1",
		flow_id: "flow-1",
		state_type: "RUNNING",
		state_name: "Running",
		start_time: new Date(now.getTime() - 5 * 60 * 1000).toISOString(),
	}),
	createFakeFlowRun({
		id: "run-5",
		name: "pending-run-1",
		flow_id: "flow-3",
		state_type: "PENDING",
		state_name: "Pending",
		start_time: new Date(now.getTime() - 2 * 60 * 1000).toISOString(),
	}),
];

const MOCK_SCHEDULED_FLOW_RUNS = [
	createFakeFlowRun({
		id: "run-6",
		name: "scheduled-run-1",
		flow_id: "flow-2",
		state_type: "SCHEDULED",
		state_name: "Late",
		expected_start_time: new Date(now.getTime() - 10 * 60 * 1000).toISOString(),
	}),
	createFakeFlowRun({
		id: "run-7",
		name: "scheduled-run-2",
		flow_id: "flow-3",
		state_type: "SCHEDULED",
		state_name: "Late",
		expected_start_time: new Date(now.getTime() - 15 * 60 * 1000).toISOString(),
	}),
];

const meta = {
	title: "Dashboard/FlowRunsAccordion",
	component: FlowRunsAccordion,
	decorators: [
		routerDecorator,
		reactQueryDecorator,
		(Story) => (
			<Suspense fallback={<div>Loading...</div>}>
				<Story />
			</Suspense>
		),
	],
} satisfies Meta<typeof FlowRunsAccordion>;

export default meta;
type Story = StoryObj<typeof meta>;

export const FailedRuns: Story = {
	args: {
		stateTypes: ["FAILED", "CRASHED"],
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json(MOCK_FAILED_FLOW_RUNS);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json(MOCK_FLOWS);
				}),
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(2);
				}),
				http.post(buildApiUrl("/flow_runs/paginate"), () => {
					return HttpResponse.json({
						results: MOCK_FAILED_FLOW_RUNS.filter(
							(r) => r.flow_id === "flow-1",
						),
						count: 2,
						pages: 1,
						page: 1,
						limit: 3,
					});
				}),
				http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
					return HttpResponse.json({
						"run-1": 5,
						"run-2": 3,
						"run-3": 2,
					});
				}),
			],
		},
	},
};

export const RunningRuns: Story = {
	args: {
		stateTypes: ["RUNNING", "PENDING"],
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json(MOCK_RUNNING_FLOW_RUNS);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json(MOCK_FLOWS);
				}),
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(1);
				}),
				http.post(buildApiUrl("/flow_runs/paginate"), () => {
					return HttpResponse.json({
						results: MOCK_RUNNING_FLOW_RUNS.filter(
							(r) => r.flow_id === "flow-1",
						),
						count: 1,
						pages: 1,
						page: 1,
						limit: 3,
					});
				}),
				http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
					return HttpResponse.json({
						"run-4": 4,
						"run-5": 1,
					});
				}),
			],
		},
	},
};

export const LateRuns: Story = {
	args: {
		stateTypes: ["SCHEDULED"],
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json(MOCK_SCHEDULED_FLOW_RUNS);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json(MOCK_FLOWS);
				}),
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(1);
				}),
				http.post(buildApiUrl("/flow_runs/paginate"), () => {
					return HttpResponse.json({
						results: MOCK_SCHEDULED_FLOW_RUNS.filter(
							(r) => r.flow_id === "flow-2",
						),
						count: 1,
						pages: 1,
						page: 1,
						limit: 3,
					});
				}),
				http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
					return HttpResponse.json({
						"run-6": 0,
						"run-7": 0,
					});
				}),
			],
		},
	},
};

export const EmptyStateFailed: Story = {
	args: {
		stateTypes: ["FAILED", "CRASHED"],
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json([]);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const EmptyStateRunning: Story = {
	args: {
		stateTypes: ["RUNNING", "PENDING", "CANCELLING"],
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json([]);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const EmptyStateCompleted: Story = {
	args: {
		stateTypes: ["COMPLETED"],
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json([]);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const EmptyStateLate: Story = {
	args: {
		stateTypes: ["SCHEDULED", "PAUSED"],
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json([]);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const EmptyStateCancelled: Story = {
	args: {
		stateTypes: ["CANCELLED"],
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json([]);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const MultipleFlows: Story = {
	args: {
		stateTypes: ["FAILED", "CRASHED"],
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json(MOCK_FAILED_FLOW_RUNS);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json(MOCK_FLOWS);
				}),
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(2);
				}),
				http.post(buildApiUrl("/flow_runs/paginate"), () => {
					return HttpResponse.json({
						results: MOCK_FAILED_FLOW_RUNS.slice(0, 2),
						count: 2,
						pages: 1,
						page: 1,
						limit: 3,
					});
				}),
				http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
					return HttpResponse.json({
						"run-1": 5,
						"run-2": 3,
						"run-3": 2,
					});
				}),
			],
		},
	},
};
