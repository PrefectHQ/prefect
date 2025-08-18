import type { Meta, StoryObj } from "@storybook/react";
import { WorkerStatusBadge } from "./worker-status-badge";

const meta = {
	title: "Components/Workers/WorkerStatusBadge",
	component: WorkerStatusBadge,
	parameters: {
		layout: "centered",
	},
	argTypes: {
		status: {
			control: { type: "select" },
			options: ["ONLINE", "OFFLINE"],
		},
	},
	args: {
		status: "ONLINE",
	},
} satisfies Meta<typeof WorkerStatusBadge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Online: Story = {
	args: {
		status: "ONLINE",
	},
};

export const Offline: Story = {
	args: {
		status: "OFFLINE",
	},
};
