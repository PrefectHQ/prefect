import type { Meta, StoryObj } from "@storybook/react";
import { createFakeFlowRun, createFakeState } from "@/mocks";
import { reactQueryDecorator, toastDecorator } from "@/storybook/utils";
import { PauseFlowRunDialog } from "./pause-flow-run-dialog";

const meta = {
	title: "Components/FlowRuns/PauseFlowRunDialog",
	component: PauseFlowRunDialog,
	decorators: [reactQueryDecorator, toastDecorator],
	args: {
		open: true,
		onOpenChange: () => {},
	},
} satisfies Meta<typeof PauseFlowRunDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		flowRun: createFakeFlowRun({
			id: "running-flow-run-id",
			name: "my-running-flow",
			state_type: "RUNNING",
			state_name: "Running",
			deployment_id: "test-deployment-id",
			state: createFakeState({
				type: "RUNNING",
				name: "Running",
			}),
		}),
	},
};
