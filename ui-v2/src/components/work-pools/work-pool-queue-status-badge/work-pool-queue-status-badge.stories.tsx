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
			options: ["ready", "paused", "not_ready"],
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

export const AllStatuses: Story = {
	args: {
		status: "ready",
	},
	render: () => (
		<div className="flex gap-4">
			<WorkPoolQueueStatusBadge status="ready" />
			<WorkPoolQueueStatusBadge status="paused" />
			<WorkPoolQueueStatusBadge status="not_ready" />
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
