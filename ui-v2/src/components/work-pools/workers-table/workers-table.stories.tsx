import type { Meta, StoryObj } from "@storybook/react";
import { HttpResponse, http } from "msw";
import { createFakeWorkPoolWorkers } from "@/mocks/create-fake-work-pool-worker";
import { WorkersTable } from "./workers-table";

const mockWorkers = createFakeWorkPoolWorkers(5, {
	work_pool_id: "test-pool-id",
});

const mockWorkersWithVariety = [
	...mockWorkers.slice(0, 2),
	{
		...mockWorkers[2],
		name: "online-worker",
		status: "ONLINE" as const,
		last_heartbeat_time: new Date().toISOString(),
	},
	{
		...mockWorkers[3],
		name: "offline-worker",
		status: "OFFLINE" as const,
		last_heartbeat_time: new Date(
			Date.now() - 24 * 60 * 60 * 1000,
		).toISOString(),
	},
	{
		...mockWorkers[4],
		name: "recent-worker",
		status: "ONLINE" as const,
		last_heartbeat_time: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
	},
];

const meta = {
	title: "Components/WorkPools/WorkersTable",
	component: WorkersTable,
	parameters: {
		layout: "padded",
	},
	args: {
		workPoolName: "test-pool",
	},
} satisfies Meta<typeof WorkersTable>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post("/api/work_pools/test-pool/workers/filter", () => {
					return HttpResponse.json(mockWorkersWithVariety);
				}),
			],
		},
	},
};

export const EmptyState: Story = {
	args: {
		workPoolName: "empty-pool",
	},
	parameters: {
		msw: {
			handlers: [
				http.post("/api/work_pools/empty-pool/workers/filter", () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const Loading: Story = {
	args: {
		workPoolName: "loading-pool",
	},
	parameters: {
		msw: {
			handlers: [
				http.post("/api/work_pools/loading-pool/workers/filter", () => {
					return new Promise(() => {}); // Never resolves
				}),
			],
		},
	},
};

export const SingleWorker: Story = {
	args: {
		workPoolName: "single-worker-pool",
	},
	parameters: {
		msw: {
			handlers: [
				http.post("/api/work_pools/single-worker-pool/workers/filter", () => {
					return HttpResponse.json([mockWorkersWithVariety[0]]);
				}),
			],
		},
	},
};

export const ManyWorkers: Story = {
	args: {
		workPoolName: "many-workers-pool",
	},
	parameters: {
		msw: {
			handlers: [
				http.post("/api/work_pools/many-workers-pool/workers/filter", () => {
					const manyWorkers = createFakeWorkPoolWorkers(50, {
						work_pool_id: "many-workers-pool-id",
					});
					return HttpResponse.json(manyWorkers);
				}),
			],
		},
	},
};
