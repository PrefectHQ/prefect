import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { createFakeFlowRun, createFakeState } from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { FlowRunDetailsPage } from ".";

type FlowRunDetailsTabOptions =
	| "Logs"
	| "TaskRuns"
	| "SubflowRuns"
	| "Artifacts"
	| "Details"
	| "Parameters"
	| "JobVariables";

const mockFlowRun = createFakeFlowRun({
	id: "flow-run-1",
	name: "my-flow-run",
	flow_id: "flow-1",
	deployment_id: "deployment-1",
	state: createFakeState({
		type: "COMPLETED",
		name: "Completed",
	}),
	parameters: {
		x: 10,
		y: 20,
	},
	tags: ["production", "etl"],
	job_variables: {
		env: "production",
	},
});

const FlowRunDetailsPageWithState = ({
	flowRunId = mockFlowRun.id,
	initialTab = "Logs" as FlowRunDetailsTabOptions,
}: {
	flowRunId?: string;
	initialTab?: FlowRunDetailsTabOptions;
}) => {
	const [tab, setTab] = useState<FlowRunDetailsTabOptions>(initialTab);

	return (
		<FlowRunDetailsPage
			id={flowRunId}
			tab={tab}
			onTabChange={(newTab) => setTab(newTab)}
		/>
	);
};

const meta = {
	title: "Components/FlowRuns/FlowRunDetailsPage",
	component: FlowRunDetailsPageWithState,
	decorators: [reactQueryDecorator, routerDecorator, toastDecorator],
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/flow_runs/:id"), () => {
					return HttpResponse.json(mockFlowRun);
				}),
			],
		},
	},
} satisfies Meta<typeof FlowRunDetailsPageWithState>;

export default meta;

type Story = StoryObj<typeof FlowRunDetailsPageWithState>;

export const Default: Story = {
	name: "Default (Logs Tab)",
	render: () => <FlowRunDetailsPageWithState />,
};

export const TaskRunsTab: Story = {
	name: "Task Runs Tab",
	render: () => <FlowRunDetailsPageWithState initialTab="TaskRuns" />,
};

export const SubflowRunsTab: Story = {
	name: "Subflow Runs Tab",
	render: () => <FlowRunDetailsPageWithState initialTab="SubflowRuns" />,
};

export const ArtifactsTab: Story = {
	name: "Artifacts Tab",
	render: () => <FlowRunDetailsPageWithState initialTab="Artifacts" />,
};

export const ParametersTab: Story = {
	name: "Parameters Tab",
	render: () => <FlowRunDetailsPageWithState initialTab="Parameters" />,
};

export const JobVariablesTab: Story = {
	name: "Job Variables Tab",
	render: () => <FlowRunDetailsPageWithState initialTab="JobVariables" />,
};

const pendingFlowRun = createFakeFlowRun({
	id: "flow-run-pending",
	name: "pending-flow-run",
	flow_id: "flow-1",
	state: createFakeState({
		type: "PENDING",
		name: "Pending",
	}),
	parameters: {
		x: 10,
	},
	tags: ["development"],
});

export const PendingRun: Story = {
	name: "Pending Run",
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/flow_runs/:id"), () => {
					return HttpResponse.json(pendingFlowRun);
				}),
			],
		},
	},
	render: () => <FlowRunDetailsPageWithState flowRunId={pendingFlowRun.id} />,
};

const runningFlowRun = createFakeFlowRun({
	id: "flow-run-running",
	name: "running-flow-run",
	flow_id: "flow-1",
	state: createFakeState({
		type: "RUNNING",
		name: "Running",
	}),
	parameters: {
		x: 10,
	},
	tags: ["development"],
});

export const RunningRun: Story = {
	name: "Running Run",
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/flow_runs/:id"), () => {
					return HttpResponse.json(runningFlowRun);
				}),
			],
		},
	},
	render: () => <FlowRunDetailsPageWithState flowRunId={runningFlowRun.id} />,
};

const failedFlowRun = createFakeFlowRun({
	id: "flow-run-failed",
	name: "failed-flow-run",
	flow_id: "flow-1",
	state: createFakeState({
		type: "FAILED",
		name: "Failed",
	}),
	parameters: {
		x: 10,
	},
	tags: ["production"],
});

export const FailedRun: Story = {
	name: "Failed Run",
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/flow_runs/:id"), () => {
					return HttpResponse.json(failedFlowRun);
				}),
			],
		},
	},
	render: () => <FlowRunDetailsPageWithState flowRunId={failedFlowRun.id} />,
};

const cancelledFlowRun = createFakeFlowRun({
	id: "flow-run-cancelled",
	name: "cancelled-flow-run",
	flow_id: "flow-1",
	state: createFakeState({
		type: "CANCELLED",
		name: "Cancelled",
	}),
	parameters: {
		x: 10,
	},
	tags: ["staging"],
});

export const CancelledRun: Story = {
	name: "Cancelled Run",
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/flow_runs/:id"), () => {
					return HttpResponse.json(cancelledFlowRun);
				}),
			],
		},
	},
	render: () => <FlowRunDetailsPageWithState flowRunId={cancelledFlowRun.id} />,
};
