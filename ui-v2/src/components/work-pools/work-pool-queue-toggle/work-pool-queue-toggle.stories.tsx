import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { createFakeWorkPoolQueue } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { WorkPoolQueueToggle } from "./work-pool-queue-toggle";

const mockQueue = createFakeWorkPoolQueue({
	name: "test-queue",
	work_pool_name: "test-pool",
	status: "READY",
});

const mockDefaultQueue = createFakeWorkPoolQueue({
	name: "default",
	work_pool_name: "test-pool",
	status: "READY",
});

const mockPausedQueue = createFakeWorkPoolQueue({
	name: "paused-queue",
	work_pool_name: "test-pool",
	status: "PAUSED",
});

const meta = {
	title: "Components/WorkPools/WorkPoolQueueToggle",
	component: WorkPoolQueueToggle,
	parameters: {
		layout: "centered",
		msw: {
			handlers: [
				http.patch(buildApiUrl("/work_queues/:id"), () => {
					return HttpResponse.json({});
				}),
			],
		},
	},
	decorators: [reactQueryDecorator],
	tags: ["autodocs"],
	argTypes: {
		onUpdate: { action: "updated" },
	},
	args: {
		onUpdate: () => console.log("Queue updated"),
	},
} satisfies Meta<typeof WorkPoolQueueToggle>;

export default meta;
type Story = StoryObj<typeof meta>;

export const ActiveQueue: Story = {
	args: {
		queue: mockQueue,
	},
};

export const PausedQueue: Story = {
	args: {
		queue: mockPausedQueue,
	},
};

export const DefaultQueue: Story = {
	args: {
		queue: mockDefaultQueue,
	},
	parameters: {
		docs: {
			description: {
				story: "The default queue cannot be paused and is always disabled.",
			},
		},
	},
};

export const DisabledToggle: Story = {
	args: {
		queue: mockQueue,
		disabled: true,
	},
	parameters: {
		docs: {
			description: {
				story: "Toggle can be disabled through the disabled prop.",
			},
		},
	},
};
