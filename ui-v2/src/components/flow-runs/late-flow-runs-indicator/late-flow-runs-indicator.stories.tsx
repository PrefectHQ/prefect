import type { Meta, StoryObj } from "@storybook/react";

import { LateFlowRunsIndicator } from "./late-flow-runs-indicator";

const meta: Meta<typeof LateFlowRunsIndicator> = {
	title: "Components/FlowRuns/LateFlowRunsIndicator",
	component: LateFlowRunsIndicator,
	parameters: {
		layout: "centered",
	},
	tags: ["autodocs"],
};

export default meta;
type Story = StoryObj<typeof LateFlowRunsIndicator>;

export const Default: Story = {
	args: {
		lateRunsCount: 3,
	},
};

export const SingleLateRun: Story = {
	args: {
		lateRunsCount: 1,
	},
};

export const ManyLateRuns: Story = {
	args: {
		lateRunsCount: 42,
	},
};

export const NoLateRuns: Story = {
	args: {
		lateRunsCount: 0,
	},
	parameters: {
		docs: {
			description: {
				story: "When there are no late runs, the component renders nothing.",
			},
		},
	},
};
