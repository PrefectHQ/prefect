import type { Meta, StoryObj } from "@storybook/react";
import { createFakeFlowRun, createFakeState } from "@/mocks";
import { reactQueryDecorator, toastDecorator } from "@/storybook/utils";
import { RetryFlowRunDialog } from "./retry-flow-run-dialog";

const meta = {
	title: "Components/FlowRuns/RetryFlowRunDialog",
	component: RetryFlowRunDialog,
	decorators: [reactQueryDecorator, toastDecorator],
	args: {
		open: true,
		onOpenChange: () => {},
	},
} satisfies Meta<typeof RetryFlowRunDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

export const FailedFlow: Story = {
	args: {
		flowRun: createFakeFlowRun({
			id: "failed-flow-run-id",
			name: "my-failed-flow",
			state_type: "FAILED",
			state_name: "Failed",
			state: createFakeState({
				type: "FAILED",
				name: "Failed",
			}),
			deployment_id: "test-deployment-id",
		}),
	},
};

export const CrashedFlow: Story = {
	args: {
		flowRun: createFakeFlowRun({
			id: "crashed-flow-run-id",
			name: "my-crashed-flow",
			state_type: "CRASHED",
			state_name: "Crashed",
			state: createFakeState({
				type: "CRASHED",
				name: "Crashed",
			}),
			deployment_id: "test-deployment-id",
		}),
	},
};

export const CancelledFlow: Story = {
	args: {
		flowRun: createFakeFlowRun({
			id: "cancelled-flow-run-id",
			name: "my-cancelled-flow",
			state_type: "CANCELLED",
			state_name: "Cancelled",
			state: createFakeState({
				type: "CANCELLED",
				name: "Cancelled",
			}),
			deployment_id: "test-deployment-id",
		}),
	},
};

export const CompletedFlow: Story = {
	args: {
		flowRun: createFakeFlowRun({
			id: "completed-flow-run-id",
			name: "my-completed-flow",
			state_type: "COMPLETED",
			state_name: "Completed",
			state: createFakeState({
				type: "COMPLETED",
				name: "Completed",
			}),
			deployment_id: "test-deployment-id",
		}),
	},
};
