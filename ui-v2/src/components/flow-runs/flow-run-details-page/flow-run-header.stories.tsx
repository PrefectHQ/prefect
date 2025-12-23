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
