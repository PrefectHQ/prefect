import type { Meta, StoryObj } from "@storybook/react";
// import { fn } from "@storybook/test";
import { HttpResponse, http } from "msw";
import { createFakeWorkPoolWorker } from "@/mocks/create-fake-work-pool-worker";
import { WorkerMenu } from "./worker-menu";

const mockWorker = createFakeWorkPoolWorker({
	name: "test-worker",
	work_pool_id: "test-pool-id",
	status: "ONLINE",
});

const meta = {
	title: "Components/Workers/WorkerMenu",
	component: WorkerMenu,
	parameters: {
		layout: "centered",
		msw: {
			handlers: [
				http.delete("/api/work_pools/test-pool/workers/:workerName", () => {
					return HttpResponse.json({});
				}),
			],
		},
	},
	args: {
		worker: mockWorker,
		workPoolName: "test-pool",
		onWorkerDeleted: () => {},
	},
} satisfies Meta<typeof WorkerMenu>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const OnlineWorker: Story = {
	args: {
		worker: {
			...mockWorker,
			name: "online-worker",
			status: "ONLINE",
		},
	},
};

export const OfflineWorker: Story = {
	args: {
		worker: {
			...mockWorker,
			name: "offline-worker",
			status: "OFFLINE",
		},
	},
};
