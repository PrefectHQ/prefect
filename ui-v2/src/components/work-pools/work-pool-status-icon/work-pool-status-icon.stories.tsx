import type { Meta, StoryObj } from "@storybook/react";

import { WorkPoolStatusIcon } from "./work-pool-status-icon";

const meta: Meta<typeof WorkPoolStatusIcon> = {
	title: "Components/WorkPools/WorkPoolStatusIcon",
	component: WorkPoolStatusIcon,
	parameters: {
		layout: "centered",
	},
	argTypes: {
		status: {
			control: "select",
			options: ["READY", "PAUSED", "NOT_READY"],
		},
		showTooltip: {
			control: "boolean",
		},
	},
};

export default meta;
type Story = StoryObj<typeof WorkPoolStatusIcon>;

export const Ready: Story = {
	args: {
		status: "READY",
	},
};

export const Paused: Story = {
	args: {
		status: "PAUSED",
	},
};

export const NotReady: Story = {
	args: {
		status: "NOT_READY",
	},
};

export const WithoutTooltip: Story = {
	args: {
		status: "READY",
		showTooltip: false,
	},
};

export const CustomSize: Story = {
	args: {
		status: "PAUSED",
		className: "h-6 w-6",
	},
};

export const AllStatuses: Story = {
	render: () => (
		<div className="flex items-center space-x-4">
			<div className="flex flex-col items-center space-y-2">
				<WorkPoolStatusIcon status="READY" />
				<span className="text-sm">Ready</span>
			</div>
			<div className="flex flex-col items-center space-y-2">
				<WorkPoolStatusIcon status="PAUSED" />
				<span className="text-sm">Paused</span>
			</div>
			<div className="flex flex-col items-center space-y-2">
				<WorkPoolStatusIcon status="NOT_READY" />
				<span className="text-sm">Not Ready</span>
			</div>
		</div>
	),
};
