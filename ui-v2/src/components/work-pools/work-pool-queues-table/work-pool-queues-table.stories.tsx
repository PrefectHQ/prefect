import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { createFakeWorkPoolQueues } from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { WorkPoolQueuesTable } from "./work-pool-queues-table";

const mockQueues = createFakeWorkPoolQueues("test-pool", 5);

const mockQueuesWithVariedStatuses = createFakeWorkPoolQueues("test-pool", 6, [
	{}, // default queue
	{ name: "high-priority", priority: 0, status: "READY" },
	{ name: "paused-queue", status: "PAUSED" },
	{ name: "not-ready-queue", status: "NOT_READY" },
	{ name: "limited-queue", concurrency_limit: 10 },
]);

const meta = {
	title: "Components/WorkPools/WorkPoolQueuesTable",
	component: WorkPoolQueuesTable,
	parameters: {
		layout: "padded",
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/test-pool/queues/filter"), () => {
					return HttpResponse.json(mockQueues);
				}),
				http.post(buildApiUrl("/work_pools/varied-pool/queues/filter"), () => {
					return HttpResponse.json(mockQueuesWithVariedStatuses);
				}),
				http.post(buildApiUrl("/work_pools/empty-pool/queues/filter"), () => {
					return HttpResponse.json([]);
				}),
				// Mutation handlers for interactions
				http.patch(buildApiUrl("/work_queues/:id"), () => {
					return HttpResponse.json({});
				}),
				http.delete(buildApiUrl("/work_queues/:id"), () => {
					return new HttpResponse(null, { status: 204 });
				}),
			],
		},
	},
	decorators: [reactQueryDecorator, routerDecorator],
	tags: ["autodocs"],
} satisfies Meta<typeof WorkPoolQueuesTable>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		workPoolName: "test-pool",
	},
};

export const WithVariedStatuses: Story = {
	args: {
		workPoolName: "varied-pool",
	},
	parameters: {
		docs: {
			description: {
				story:
					"Shows queues with different statuses, priorities, and concurrency limits.",
			},
		},
	},
};

export const EmptyState: Story = {
	args: {
		workPoolName: "empty-pool",
	},
	parameters: {
		docs: {
			description: {
				story: "Shows the empty state when no queues exist for the work pool.",
			},
		},
	},
};
