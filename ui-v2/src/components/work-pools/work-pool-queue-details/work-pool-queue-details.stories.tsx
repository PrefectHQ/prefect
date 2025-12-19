import type { Meta, StoryObj } from "@storybook/react";
import { createFakeWorkPoolQueue } from "@/mocks";
import { WorkPoolQueueDetails } from "./work-pool-queue-details";

const meta = {
	title: "Components/WorkPools/WorkPoolQueueDetails",
	component: WorkPoolQueueDetails,
	parameters: {
		layout: "padded",
	},
	decorators: [
		(Story) => (
			<div className="max-w-4xl">
				<Story />
			</div>
		),
	],
	tags: ["autodocs"],
} satisfies Meta<typeof WorkPoolQueueDetails>;

export default meta;
type Story = StoryObj<typeof meta>;

const mockQueue = createFakeWorkPoolQueue({
	id: "queue-123",
	name: "default",
	description: "Default queue for processing flow runs",
	priority: 1,
	concurrency_limit: 50,
	status: "READY",
	created: "2024-01-15T10:00:00Z",
	updated: "2024-01-20T15:30:00Z",
	last_polled: "2024-01-20T16:00:00Z",
	work_pool_name: "production-docker-pool",
});

export const Default: Story = {
	args: {
		workPoolName: "production-docker-pool",
		queue: mockQueue,
	},
};

export const WithNullValues: Story = {
	args: {
		workPoolName: "production-docker-pool",
		queue: createFakeWorkPoolQueue({
			id: "queue-456",
			name: "secondary-queue",
			description: null,
			priority: 2,
			concurrency_limit: null,
			status: "NOT_READY",
			created: "2024-01-15T10:00:00Z",
			updated: "2024-01-20T15:30:00Z",
			last_polled: null,
			work_pool_name: "production-docker-pool",
		}),
	},
};

export const PausedQueue: Story = {
	args: {
		workPoolName: "production-docker-pool",
		queue: createFakeWorkPoolQueue({
			id: "queue-789",
			name: "paused-queue",
			description: "This queue is currently paused",
			priority: 3,
			concurrency_limit: 25,
			status: "PAUSED",
			is_paused: true,
			created: "2024-01-15T10:00:00Z",
			updated: "2024-01-20T15:30:00Z",
			last_polled: "2024-01-19T12:00:00Z",
			work_pool_name: "production-docker-pool",
		}),
	},
};

export const NotReadyQueue: Story = {
	args: {
		workPoolName: "production-docker-pool",
		queue: createFakeWorkPoolQueue({
			id: "queue-not-ready",
			name: "not-ready-queue",
			description: "Queue without active workers",
			priority: 5,
			concurrency_limit: 10,
			status: "NOT_READY",
			created: "2024-01-15T10:00:00Z",
			updated: "2024-01-20T15:30:00Z",
			last_polled: null,
			work_pool_name: "production-docker-pool",
		}),
	},
};

export const AlternateSpacing: Story = {
	args: {
		workPoolName: "production-docker-pool",
		queue: mockQueue,
		alternate: true,
	},
};

export const UnlimitedConcurrency: Story = {
	args: {
		workPoolName: "production-docker-pool",
		queue: createFakeWorkPoolQueue({
			id: "queue-unlimited",
			name: "unlimited-queue",
			description: "Queue with unlimited concurrency",
			priority: 1,
			concurrency_limit: null,
			status: "READY",
			created: "2024-01-15T10:00:00Z",
			updated: "2024-01-20T15:30:00Z",
			last_polled: "2024-01-20T16:00:00Z",
			work_pool_name: "production-docker-pool",
		}),
	},
};

export const HighPriority: Story = {
	args: {
		workPoolName: "production-docker-pool",
		queue: createFakeWorkPoolQueue({
			id: "queue-high-priority",
			name: "high-priority-queue",
			description: "High priority queue for critical flows",
			priority: 10,
			concurrency_limit: 100,
			status: "READY",
			created: "2024-01-15T10:00:00Z",
			updated: "2024-01-20T15:30:00Z",
			last_polled: "2024-01-20T16:00:00Z",
			work_pool_name: "production-docker-pool",
		}),
	},
};
