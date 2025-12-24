import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { createFakeFlow, createFakeFlowRun, createFakeState } from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunSubflows } from "./flow-run-subflows";

const mockParentFlowRunId = "parent-flow-run-1";

const mockFlows = [
	createFakeFlow({ id: "flow-1", name: "etl-pipeline" }),
	createFakeFlow({ id: "flow-2", name: "data-processor" }),
	createFakeFlow({ id: "flow-3", name: "report-generator" }),
];

const mockSubflowRuns = [
	createFakeFlowRun({
		id: "subflow-1",
		name: "etl-pipeline-run-1",
		flow_id: "flow-1",
		state: createFakeState({ type: "COMPLETED", name: "Completed" }),
	}),
	createFakeFlowRun({
		id: "subflow-2",
		name: "data-processor-run-1",
		flow_id: "flow-2",
		state: createFakeState({ type: "RUNNING", name: "Running" }),
	}),
	createFakeFlowRun({
		id: "subflow-3",
		name: "report-generator-run-1",
		flow_id: "flow-3",
		state: createFakeState({ type: "FAILED", name: "Failed" }),
	}),
];

const mockManySubflowRuns = Array.from({ length: 25 }, (_, i) =>
	createFakeFlowRun({
		id: `subflow-${i + 1}`,
		name: `subflow-run-${i + 1}`,
		flow_id: mockFlows[i % 3].id,
		state: createFakeState({
			type: i % 3 === 0 ? "COMPLETED" : i % 3 === 1 ? "RUNNING" : "FAILED",
			name: i % 3 === 0 ? "Completed" : i % 3 === 1 ? "Running" : "Failed",
		}),
	}),
);

const meta = {
	title: "Components/FlowRuns/FlowRunSubflows",
	component: FlowRunSubflows,
	decorators: [routerDecorator, reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(3);
				}),
				http.post(buildApiUrl("/flow_runs/paginate"), () => {
					return HttpResponse.json({
						results: mockSubflowRuns,
						count: 3,
						pages: 1,
						page: 1,
						limit: 10,
					});
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json(mockFlows);
				}),
			],
		},
	},
} satisfies Meta<typeof FlowRunSubflows>;

export default meta;
type Story = StoryObj<typeof FlowRunSubflows>;

export const Default: Story = {
	args: {
		parentFlowRunId: mockParentFlowRunId,
	},
};

export const Empty: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(0);
				}),
				http.post(buildApiUrl("/flow_runs/paginate"), () => {
					return HttpResponse.json({
						results: [],
						count: 0,
						pages: 0,
						page: 1,
						limit: 10,
					});
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
	args: {
		parentFlowRunId: "empty-parent-flow-run",
	},
};

export const WithMultiplePages: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(25);
				}),
				http.post(buildApiUrl("/flow_runs/paginate"), () => {
					return HttpResponse.json({
						results: mockManySubflowRuns.slice(0, 10),
						count: 25,
						pages: 3,
						page: 1,
						limit: 10,
					});
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json(mockFlows);
				}),
			],
		},
	},
	args: {
		parentFlowRunId: "parent-with-many-subflows",
	},
};

export const SingleSubflow: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(1);
				}),
				http.post(buildApiUrl("/flow_runs/paginate"), () => {
					return HttpResponse.json({
						results: [mockSubflowRuns[0]],
						count: 1,
						pages: 1,
						page: 1,
						limit: 10,
					});
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json([mockFlows[0]]);
				}),
			],
		},
	},
	args: {
		parentFlowRunId: "parent-with-single-subflow",
	},
};
