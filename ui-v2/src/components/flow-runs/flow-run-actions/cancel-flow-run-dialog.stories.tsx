import type { Meta, StoryObj } from "@storybook/react";
import { createFakeFlowRun, createFakeState } from "@/mocks";
import { reactQueryDecorator, toastDecorator } from "@/storybook/utils";
import { CancelFlowRunDialog } from "./cancel-flow-run-dialog";

const meta = {
	title: "Components/FlowRuns/CancelFlowRunDialog",
	component: CancelFlowRunDialog,
	decorators: [reactQueryDecorator, toastDecorator],
	args: {
		open: true,
		onOpenChange: () => {},
	},
} satisfies Meta<typeof CancelFlowRunDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		flowRun: createFakeFlowRun({
			id: "running-flow-run-id",
			name: "my-flow-run",
			state_type: "RUNNING",
			state_name: "Running",
			state: createFakeState({
				type: "RUNNING",
				name: "Running",
			}),
		}),
	},
};

export const ScheduledFlow: Story = {
	args: {
		flowRun: createFakeFlowRun({
			id: "scheduled-flow-run-id",
			name: "scheduled-flow-run",
			state_type: "SCHEDULED",
			state_name: "Scheduled",
			state: createFakeState({
				type: "SCHEDULED",
				name: "Scheduled",
			}),
		}),
	},
};

export const PausedFlow: Story = {
	args: {
		flowRun: createFakeFlowRun({
			id: "paused-flow-run-id",
			name: "paused-flow-run",
			state_type: "PAUSED",
			state_name: "Paused",
			state: createFakeState({
				type: "PAUSED",
				name: "Paused",
			}),
		}),
	},
};

export const PendingFlow: Story = {
	args: {
		flowRun: createFakeFlowRun({
			id: "pending-flow-run-id",
			name: "pending-flow-run",
			state_type: "PENDING",
			state_name: "Pending",
			state: createFakeState({
				type: "PENDING",
				name: "Pending",
			}),
		}),
	},
};
