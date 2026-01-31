import type { Meta, StoryObj } from "@storybook/react";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunGraphStatePopover } from "./flow-run-graph-state-popover";

const meta = {
	component: FlowRunGraphStatePopover,
	title: "Components/FlowRuns/FlowRunGraphStatePopover",
	decorators: [reactQueryDecorator, routerDecorator],
	parameters: {
		layout: "centered",
	},
} satisfies Meta<typeof FlowRunGraphStatePopover>;

export default meta;

type Story = StoryObj<typeof meta>;

const createStateSelection = (
	type: string,
	name: string,
	timestamp: Date = new Date("2024-01-15T10:30:00Z"),
) => ({
	kind: "state" as const,
	id: `state-${type.toLowerCase()}`,
	type: type as
		| "COMPLETED"
		| "FAILED"
		| "RUNNING"
		| "CANCELLED"
		| "CRASHED"
		| "PAUSED"
		| "PENDING"
		| "SCHEDULED"
		| "CANCELLING",
	name,
	timestamp,
	position: { x: 200, y: 100, width: 20, height: 20 },
});

export const Default: Story = {
	args: {
		selection: createStateSelection("COMPLETED", "Completed"),
		onClose: () => console.log("Close clicked"),
	},
};

export const Failed: Story = {
	args: {
		selection: createStateSelection("FAILED", "Failed"),
		onClose: () => console.log("Close clicked"),
	},
};

export const Running: Story = {
	args: {
		selection: createStateSelection("RUNNING", "Running"),
		onClose: () => console.log("Close clicked"),
	},
};

export const Scheduled: Story = {
	args: {
		selection: createStateSelection("SCHEDULED", "Scheduled"),
		onClose: () => console.log("Close clicked"),
	},
};

export const Pending: Story = {
	args: {
		selection: createStateSelection("PENDING", "Pending"),
		onClose: () => console.log("Close clicked"),
	},
};

export const Cancelled: Story = {
	args: {
		selection: createStateSelection("CANCELLED", "Cancelled"),
		onClose: () => console.log("Close clicked"),
	},
};

export const Crashed: Story = {
	args: {
		selection: createStateSelection("CRASHED", "Crashed"),
		onClose: () => console.log("Close clicked"),
	},
};

export const Paused: Story = {
	args: {
		selection: createStateSelection("PAUSED", "Paused"),
		onClose: () => console.log("Close clicked"),
	},
};

export const CustomStateName: Story = {
	args: {
		selection: createStateSelection("COMPLETED", "AwaitingRetry"),
		onClose: () => console.log("Close clicked"),
	},
};
