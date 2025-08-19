import type { Meta, StoryObj } from "@storybook/react";
import { WorkPoolQueueStatusBadge } from "./work-pool-queue-status-badge";

const meta = {
	title: "Components/WorkPools/WorkPoolQueueStatusBadge",
	component: WorkPoolQueueStatusBadge,
	parameters: {
		layout: "centered",
	},
	tags: ["autodocs"],
	argTypes: {
		status: {
			control: "select",
			options: ["READY", "PAUSED", "NOT_READY"],
		},
		className: {
			control: "text",
		},
	},
} satisfies Meta<typeof WorkPoolQueueStatusBadge>;

export default meta;
type Story = StoryObj<typeof meta>;

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
	args: {
		status: "READY",
	},
	render: () => (
		<div className="flex gap-4">
			<WorkPoolQueueStatusBadge status="READY" />
			<WorkPoolQueueStatusBadge status="PAUSED" />
			<WorkPoolQueueStatusBadge status="NOT_READY" />
		</div>
	),
	parameters: {
		docs: {
			description: {
				story:
					"Hover over each badge to see the tooltip with status explanation.",
			},
		},
	},
};
