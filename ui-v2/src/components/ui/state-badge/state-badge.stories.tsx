import type { Meta, StoryObj } from "@storybook/react";
import { StateBadge } from ".";

const meta = {
	title: "UI/StateBadge",
	component: StateBadge,
	argTypes: {
		state: {
			options: [
				"COMPLETED",
				"FAILED",
				"RUNNING",
				"PENDING",
				"PAUSED",
				"CANCELLED",
				"CANCELLING",
				"CRASHED",
				"SCHEDULED",
				"LATE",
			],
			mapping: {
				COMPLETED: { type: "COMPLETED", name: "Completed" },
				FAILED: { type: "FAILED", name: "Failed" },
				RUNNING: { type: "RUNNING", name: "Running" },
				PENDING: { type: "PENDING", name: "Pending" },
				PAUSED: { type: "PAUSED", name: "Paused" },
				CANCELLED: { type: "CANCELLED", name: "Cancelled" },
				CANCELLING: { type: "CANCELLING", name: "Cancelling" },
				CRASHED: { type: "CRASHED", name: "Crashed" },
				SCHEDULED: { type: "SCHEDULED", name: "Scheduled" },
				LATE: { type: "SCHEDULED", name: "Late" },
			},
		},
	},
} satisfies Meta<typeof StateBadge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const States: Story = {
	args: {
		state: {
			type: "COMPLETED",
			name: "Completed",
		},
	},
};
