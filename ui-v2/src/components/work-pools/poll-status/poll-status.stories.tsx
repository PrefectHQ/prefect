import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { reactQueryDecorator } from "@/storybook/utils";
import { PollStatus } from "./poll-status";

const meta = {
	title: "Components/WorkPools/PollStatus",
	component: PollStatus,
	parameters: {
		layout: "centered",
	},
	decorators: [reactQueryDecorator],
	tags: ["autodocs"],
} satisfies Meta<typeof PollStatus>;

export default meta;
type Story = StoryObj<typeof meta>;

export const WithWorkers: Story = {
	args: {
		workPoolName: "my-work-pool",
	},
	parameters: {
		msw: {
			handlers: [
				http.post(
					buildApiUrl("/work_pools/my-work-pool/workers/filter"),
					() => {
						return HttpResponse.json([
							{
								id: "worker1",
								name: "Worker 1",
								created: "2024-01-15T10:00:00Z",
								updated: "2024-01-15T10:30:00Z",
								work_pool_id: "my-work-pool",
								last_heartbeat_time: "2024-01-15T10:30:00Z",
								heartbeat_interval_seconds: 30,
								status: "ONLINE",
							},
							{
								id: "worker2",
								name: "Worker 2",
								created: "2024-01-15T10:00:00Z",
								updated: "2024-01-15T10:25:00Z",
								work_pool_id: "my-work-pool",
								last_heartbeat_time: "2024-01-15T10:25:00Z",
								heartbeat_interval_seconds: 30,
								status: "ONLINE",
							},
						]);
					},
				),
			],
		},
	},
};

export const WithoutWorkers: Story = {
	args: {
		workPoolName: "empty-work-pool",
	},
	parameters: {
		msw: {
			handlers: [
				http.post(
					buildApiUrl("/work_pools/empty-work-pool/workers/filter"),
					() => {
						return HttpResponse.json([]);
					},
				),
			],
		},
	},
};

export const NoRecentActivity: Story = {
	args: {
		workPoolName: "inactive-work-pool",
	},
	parameters: {
		msw: {
			handlers: [
				http.post(
					buildApiUrl("/work_pools/inactive-work-pool/workers/filter"),
					() => {
						return HttpResponse.json([
							{
								id: "worker1",
								name: "Worker 1",
								created: "2024-01-15T10:00:00Z",
								updated: "2024-01-15T10:25:00Z",
								work_pool_id: "inactive-work-pool",
								last_heartbeat_time: null,
								heartbeat_interval_seconds: 30,
								status: "OFFLINE",
							},
						]);
					},
				),
			],
		},
	},
};
