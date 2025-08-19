import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
// import { fn } from "@storybook/test";
import { HttpResponse, http } from "msw";
import { createFakeWorkPoolWorker } from "@/mocks/create-fake-work-pool-worker";
import { reactQueryDecorator } from "@/storybook/utils/react-query-decorator";
import { toastDecorator } from "@/storybook/utils/toast-decorator";
import { WorkerMenu } from "./worker-menu";

const mockWorker = createFakeWorkPoolWorker({
	name: "test-worker",
	work_pool_id: "test-pool-id",
	status: "ONLINE",
});

const meta = {
	title: "Components/Workers/WorkerMenu",
	component: WorkerMenu,
	decorators: [toastDecorator, reactQueryDecorator],
	parameters: {
		layout: "centered",
		msw: {
			handlers: [
				http.delete(
					buildApiUrl("/work_pools/:workPoolName/workers/:name"),
					() => {
						return HttpResponse.json({});
					},
				),
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
