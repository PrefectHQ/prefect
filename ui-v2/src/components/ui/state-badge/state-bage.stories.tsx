import type { Meta, StoryObj } from "@storybook/react";
import { StateBadge } from ".";

const meta = {
	title: "UI/StateBadge",
	component: StateBadge,
	parameters: {
		layout: "centered",
	},
} satisfies Meta<typeof StateBadge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Completed: Story = {
	args: {
		state: {
			type: "COMPLETED",
			name: "Completed",
		},
	},
};

export const Failed: Story = {
	args: {
		state: {
			type: "FAILED",
			name: "Failed",
		},
	},
};

export const Running: Story = {
	args: {
		state: {
			type: "RUNNING",
			name: "Running",
		},
	},
};

export const Pending: Story = {
	args: {
		state: {
			type: "PENDING",
			name: "Pending",
		},
	},
};

export const Paused: Story = {
	args: {
		state: {
			type: "PAUSED",
			name: "Paused",
		},
	},
};

export const Cancelled: Story = {
	args: {
		state: {
			type: "CANCELLED",
			name: "Cancelled",
		},
	},
};

export const Cancelling: Story = {
	args: {
		state: {
			type: "CANCELLING",
			name: "Cancelling",
		},
	},
};

export const Crashed: Story = {
	args: {
		state: {
			type: "CRASHED",
			name: "Crashed",
		},
	},
};

export const Scheduled: Story = {
	args: {
		state: {
			type: "SCHEDULED",
			name: "Scheduled",
		},
	},
};

export const Late: Story = {
	args: {
		state: {
			type: "SCHEDULED",
			name: "Late",
		},
	},
};
