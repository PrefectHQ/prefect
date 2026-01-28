import type { Meta, StoryObj } from "@storybook/react";
import { createFakeFlowRun, createFakeState } from "@/mocks";
import { reactQueryDecorator, toastDecorator } from "@/storybook/utils";
import { ResumeFlowRunDialog } from "./resume-flow-run-dialog";

const meta = {
	title: "Components/FlowRuns/ResumeFlowRunDialog",
	component: ResumeFlowRunDialog,
	decorators: [reactQueryDecorator, toastDecorator],
	args: {
		open: true,
		onOpenChange: () => {},
	},
} satisfies Meta<typeof ResumeFlowRunDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

export const SimpleResume: Story = {
	args: {
		flowRun: createFakeFlowRun({
			id: "paused-flow-run-id",
			name: "my-paused-flow",
			state_type: "PAUSED",
			state_name: "Paused",
			state: createFakeState({
				type: "PAUSED",
				name: "Paused",
			}),
		}),
	},
};

export const SuspendedFlow: Story = {
	args: {
		flowRun: createFakeFlowRun({
			id: "suspended-flow-run-id",
			name: "my-suspended-flow",
			state_type: "PAUSED",
			state_name: "Suspended",
			state: createFakeState({
				type: "PAUSED",
				name: "Suspended",
			}),
		}),
	},
};
