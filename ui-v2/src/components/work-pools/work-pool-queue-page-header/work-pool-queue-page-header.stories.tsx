import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { fn } from "storybook/test";
import { createFakeWorkPoolQueue } from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { WorkPoolQueuePageHeader } from "./work-pool-queue-page-header";

const mockQueue = createFakeWorkPoolQueue({
	name: "my-queue",
	work_pool_name: "my-work-pool",
	status: "READY",
	is_paused: false,
});

const mockPausedQueue = createFakeWorkPoolQueue({
	name: "paused-queue",
	work_pool_name: "my-work-pool",
	status: "PAUSED",
	is_paused: true,
});

const mockDefaultQueue = createFakeWorkPoolQueue({
	name: "default",
	work_pool_name: "my-work-pool",
	status: "READY",
	is_paused: false,
});

const meta: Meta<typeof WorkPoolQueuePageHeader> = {
	title: "Components/WorkPools/WorkPoolQueuePageHeader",
	component: WorkPoolQueuePageHeader,
	decorators: [reactQueryDecorator, routerDecorator],
	parameters: {
		layout: "padded",
		msw: {
			handlers: [
				http.patch(
					buildApiUrl("/work_pools/:workPoolName/queues/:queueName"),
					() => {
						return HttpResponse.json({});
					},
				),
				http.delete(
					buildApiUrl("/work_pools/:workPoolName/queues/:queueName"),
					() => {
						return HttpResponse.json({});
					},
				),
			],
		},
	},
	args: {
		onUpdate: fn(),
	},
};

export default meta;
type Story = StoryObj<typeof WorkPoolQueuePageHeader>;

export const Default: Story = {
	args: {
		workPoolName: "my-work-pool",
		queue: mockQueue,
	},
};

export const Paused: Story = {
	args: {
		workPoolName: "my-work-pool",
		queue: mockPausedQueue,
	},
};

export const DefaultQueue: Story = {
	args: {
		workPoolName: "my-work-pool",
		queue: mockDefaultQueue,
	},
	parameters: {
		docs: {
			description: {
				story: "The default queue has special behavior - it cannot be deleted.",
			},
		},
	},
};

export const LongNames: Story = {
	args: {
		workPoolName: "very-long-work-pool-name-that-might-wrap-or-truncate",
		queue: createFakeWorkPoolQueue({
			name: "very-long-queue-name-that-might-wrap-or-truncate",
			work_pool_name: "very-long-work-pool-name-that-might-wrap-or-truncate",
			status: "READY",
		}),
	},
};

export const WithHighPriority: Story = {
	args: {
		workPoolName: "my-work-pool",
		queue: createFakeWorkPoolQueue({
			name: "high-priority-queue",
			work_pool_name: "my-work-pool",
			status: "READY",
			priority: 10,
		}),
	},
};

export const WithConcurrencyLimit: Story = {
	args: {
		workPoolName: "my-work-pool",
		queue: createFakeWorkPoolQueue({
			name: "limited-queue",
			work_pool_name: "my-work-pool",
			status: "READY",
			concurrency_limit: 50,
		}),
	},
};
