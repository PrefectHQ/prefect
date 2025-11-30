import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import {
	createFakeDeployment,
	createFakeFlow,
	createFakeFlowRun,
} from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunsCard } from "./index";

const MOCK_FLOWS = [
	createFakeFlow({ id: "flow-1", name: "ETL Pipeline" }),
	createFakeFlow({ id: "flow-2", name: "Data Sync" }),
];

const MOCK_DEPLOYMENTS = [
	createFakeDeployment({ id: "deployment-1", name: "Production ETL" }),
	createFakeDeployment({ id: "deployment-2", name: "Staging Sync" }),
];

const now = new Date();
const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);

const MOCK_FLOW_RUNS = [
	createFakeFlowRun({
		id: "run-1",
		name: "completed-run-1",
		flow_id: "flow-1",
		deployment_id: "deployment-1",
		state_type: "COMPLETED",
		state_name: "Completed",
		state: { type: "COMPLETED", name: "Completed", id: "state-1" },
		start_time: new Date(now.getTime() - 1 * 60 * 60 * 1000).toISOString(),
		end_time: new Date(now.getTime() - 30 * 60 * 1000).toISOString(),
	}),
	createFakeFlowRun({
		id: "run-2",
		name: "failed-run-1",
		flow_id: "flow-1",
		deployment_id: "deployment-1",
		state_type: "FAILED",
		state_name: "Failed",
		state: { type: "FAILED", name: "Failed", id: "state-2" },
		start_time: new Date(now.getTime() - 2 * 60 * 60 * 1000).toISOString(),
		end_time: new Date(now.getTime() - 1.5 * 60 * 60 * 1000).toISOString(),
	}),
	createFakeFlowRun({
		id: "run-3",
		name: "running-run-1",
		flow_id: "flow-2",
		deployment_id: "deployment-2",
		state_type: "RUNNING",
		state_name: "Running",
		state: { type: "RUNNING", name: "Running", id: "state-3" },
		start_time: new Date(now.getTime() - 10 * 60 * 1000).toISOString(),
		end_time: null,
	}),
	createFakeFlowRun({
		id: "run-4",
		name: "scheduled-run-1",
		flow_id: "flow-2",
		deployment_id: "deployment-2",
		state_type: "SCHEDULED",
		state_name: "Scheduled",
		state: { type: "SCHEDULED", name: "Scheduled", id: "state-4" },
		start_time: null,
		end_time: null,
		expected_start_time: new Date(now.getTime() + 30 * 60 * 1000).toISOString(),
	}),
	createFakeFlowRun({
		id: "run-5",
		name: "completed-run-2",
		flow_id: "flow-1",
		deployment_id: "deployment-1",
		state_type: "COMPLETED",
		state_name: "Completed",
		state: { type: "COMPLETED", name: "Completed", id: "state-5" },
		start_time: new Date(now.getTime() - 3 * 60 * 60 * 1000).toISOString(),
		end_time: new Date(now.getTime() - 2.5 * 60 * 60 * 1000).toISOString(),
	}),
];

const meta = {
	title: "Dashboard/FlowRunsCard",
	component: FlowRunsCard,
	decorators: [routerDecorator, reactQueryDecorator],
} satisfies Meta<typeof FlowRunsCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		filter: {
			startDate: sevenDaysAgo.toISOString(),
			endDate: now.toISOString(),
		},
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json(MOCK_FLOW_RUNS);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json(MOCK_FLOWS);
				}),
				http.post(buildApiUrl("/deployments/filter"), () => {
					return HttpResponse.json(MOCK_DEPLOYMENTS);
				}),
			],
		},
	},
};

export const Empty: Story = {
	args: {
		filter: {
			startDate: sevenDaysAgo.toISOString(),
			endDate: now.toISOString(),
		},
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
				http.post(buildApiUrl("/deployments/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const WithError: Story = {
	args: {
		filter: {
			startDate: sevenDaysAgo.toISOString(),
			endDate: now.toISOString(),
		},
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.error();
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json([]);
				}),
				http.post(buildApiUrl("/deployments/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};
