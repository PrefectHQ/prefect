import type { Meta, StoryObj } from "@storybook/react";

import { WorkPoolStatusBadge } from "./work-pool-status-badge";

const meta: Meta<typeof WorkPoolStatusBadge> = {
	title: "Components/WorkPools/WorkPoolStatusBadge",
	component: WorkPoolStatusBadge,
	parameters: {
		layout: "centered",
	},
	argTypes: {
		status: {
			control: "select",
			options: ["READY", "PAUSED", "NOT_READY"],
		},
	},
};

export default meta;
type Story = StoryObj<typeof WorkPoolStatusBadge>;

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

export const AllStatuses: Story = {
	render: () => (
		<div className="flex flex-col space-y-2">
			<div className="flex items-center space-x-2">
				<WorkPoolStatusBadge status="READY" />
				<span className="text-sm text-muted-foreground">
					Work pool is ready and accepting work
				</span>
			</div>
			<div className="flex items-center space-x-2">
				<WorkPoolStatusBadge status="PAUSED" />
				<span className="text-sm text-muted-foreground">
					Work pool is paused
				</span>
			</div>
			<div className="flex items-center space-x-2">
				<WorkPoolStatusBadge status="NOT_READY" />
				<span className="text-sm text-muted-foreground">
					Work pool is not ready
				</span>
			</div>
		</div>
	),
};

export const InContext: Story = {
	render: () => (
		<div className="max-w-md p-4 border rounded-lg">
			<div className="flex items-center justify-between mb-2">
				<h3 className="font-semibold">My Work Pool</h3>
				<WorkPoolStatusBadge status="READY" />
			</div>
			<p className="text-sm text-muted-foreground">
				A sample work pool demonstrating the status badge in context.
			</p>
		</div>
	),
};
