import type { Meta, StoryObj } from "@storybook/react";
import { createFakeFlowRun, createFakeState } from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { FlowRunHeader } from "./flow-run-header";

const meta = {
	title: "Components/FlowRuns/FlowRunHeader",
	component: FlowRunHeader,
	decorators: [reactQueryDecorator, routerDecorator, toastDecorator],
	args: {
		onDeleteClick: () => {},
	},
} satisfies Meta<typeof FlowRunHeader>;

export default meta;

type Story = StoryObj<typeof FlowRunHeader>;

export const Completed: Story = {
	name: "Completed State",
	args: {
		flowRun: createFakeFlowRun({
			id: "flow-run-completed",
			name: "my-completed-flow-run",
			state_type: "COMPLETED",
			state_name: "Completed",
			state: createFakeState({
				type: "COMPLETED",
				name: "Completed",
			}),
		}),
	},
};

export const Running: Story = {
	name: "Running State",
	args: {
		flowRun: createFakeFlowRun({
			id: "flow-run-running",
			name: "my-running-flow-run",
			state_type: "RUNNING",
			state_name: "Running",
			state: createFakeState({
				type: "RUNNING",
				name: "Running",
			}),
		}),
	},
};

export const Failed: Story = {
	name: "Failed State",
	args: {
		flowRun: createFakeFlowRun({
			id: "flow-run-failed",
			name: "my-failed-flow-run",
			state_type: "FAILED",
			state_name: "Failed",
			state: createFakeState({
				type: "FAILED",
				name: "Failed",
			}),
		}),
	},
};

export const Pending: Story = {
	name: "Pending State",
	args: {
		flowRun: createFakeFlowRun({
			id: "flow-run-pending",
			name: "my-pending-flow-run",
			state_type: "PENDING",
			state_name: "Pending",
			state: createFakeState({
				type: "PENDING",
				name: "Pending",
			}),
		}),
	},
};

export const Cancelled: Story = {
	name: "Cancelled State",
	args: {
		flowRun: createFakeFlowRun({
			id: "flow-run-cancelled",
			name: "my-cancelled-flow-run",
			state_type: "CANCELLED",
			state_name: "Cancelled",
			state: createFakeState({
				type: "CANCELLED",
				name: "Cancelled",
			}),
		}),
	},
};

export const Scheduled: Story = {
	name: "Scheduled State",
	args: {
		flowRun: createFakeFlowRun({
			id: "flow-run-scheduled",
			name: "my-scheduled-flow-run",
			state_type: "SCHEDULED",
			state_name: "Scheduled",
			state: createFakeState({
				type: "SCHEDULED",
				name: "Scheduled",
			}),
		}),
	},
};

export const Crashed: Story = {
	name: "Crashed State",
	args: {
		flowRun: createFakeFlowRun({
			id: "flow-run-crashed",
			name: "my-crashed-flow-run",
			state_type: "CRASHED",
			state_name: "Crashed",
			state: createFakeState({
				type: "CRASHED",
				name: "Crashed",
			}),
		}),
	},
};

export const WithAllRelationships: Story = {
	name: "With All Relationships",
	args: {
		flowRun: createFakeFlowRun({
			id: "flow-run-all-relationships",
			name: "my-flow-run-with-all-relationships",
			flow_id: "test-flow-id",
			deployment_id: "test-deployment-id",
			work_pool_name: "my-work-pool",
			work_queue_name: "default",
			parent_task_run_id: "parent-task-run-id",
			state_type: "COMPLETED",
			state_name: "Completed",
			state: createFakeState({
				type: "COMPLETED",
				name: "Completed",
			}),
		}),
	},
};

export const WithFlowAndDeploymentOnly: Story = {
	name: "With Flow and Deployment Only",
	args: {
		flowRun: createFakeFlowRun({
			id: "flow-run-flow-deployment",
			name: "my-flow-run-flow-deployment",
			flow_id: "test-flow-id",
			deployment_id: "test-deployment-id",
			work_pool_name: null,
			work_queue_name: null,
			parent_task_run_id: null,
			state_type: "COMPLETED",
			state_name: "Completed",
			state: createFakeState({
				type: "COMPLETED",
				name: "Completed",
			}),
		}),
	},
};

export const WithWorkPoolNoQueue: Story = {
	name: "With Work Pool but No Queue",
	args: {
		flowRun: createFakeFlowRun({
			id: "flow-run-work-pool-no-queue",
			name: "my-flow-run-work-pool-no-queue",
			flow_id: "test-flow-id",
			deployment_id: "test-deployment-id",
			work_pool_name: "my-work-pool",
			work_queue_name: null,
			parent_task_run_id: null,
			state_type: "RUNNING",
			state_name: "Running",
			state: createFakeState({
				type: "RUNNING",
				name: "Running",
			}),
		}),
	},
};

export const WithParentRun: Story = {
	name: "With Parent Run",
	args: {
		flowRun: createFakeFlowRun({
			id: "flow-run-with-parent",
			name: "my-subflow-run",
			flow_id: "test-flow-id",
			deployment_id: null,
			work_pool_name: null,
			work_queue_name: null,
			parent_task_run_id: "parent-task-run-id",
			state_type: "COMPLETED",
			state_name: "Completed",
			state: createFakeState({
				type: "COMPLETED",
				name: "Completed",
			}),
		}),
	},
};

export const MinimalRelationships: Story = {
	name: "Minimal Relationships (Flow Only)",
	args: {
		flowRun: createFakeFlowRun({
			id: "flow-run-minimal",
			name: "my-minimal-flow-run",
			flow_id: "test-flow-id",
			deployment_id: null,
			work_pool_name: null,
			work_queue_name: null,
			parent_task_run_id: null,
			state_type: "PENDING",
			state_name: "Pending",
			state: createFakeState({
				type: "PENDING",
				name: "Pending",
			}),
		}),
	},
};
