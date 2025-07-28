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
			options: ["ready", "paused", "not_ready"],
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
		status: "ready",
	},
};

export const Paused: Story = {
	args: {
		status: "paused",
	},
};

export const NotReady: Story = {
	args: {
		status: "not_ready",
	},
};

export const WithoutTooltip: Story = {
	args: {
		status: "ready",
		showTooltip: false,
	},
};

export const CustomSize: Story = {
	args: {
		status: "paused",
		className: "h-6 w-6",
	},
};

export const AllStatuses: Story = {
	render: () => (
		<div className="flex items-center space-x-4">
			<div className="flex flex-col items-center space-y-2">
				<WorkPoolStatusIcon status="ready" />
				<span className="text-sm">Ready</span>
			</div>
			<div className="flex flex-col items-center space-y-2">
				<WorkPoolStatusIcon status="paused" />
				<span className="text-sm">Paused</span>
			</div>
			<div className="flex flex-col items-center space-y-2">
				<WorkPoolStatusIcon status="not_ready" />
				<span className="text-sm">Not Ready</span>
			</div>
		</div>
	),
};
