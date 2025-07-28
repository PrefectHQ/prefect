import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { WorkerMonitoring } from "./worker-monitoring";

const queryClient = new QueryClient();

const meta = {
	title: "Components/WorkPools/WorkerMonitoring",
	component: WorkerMonitoring,
	parameters: {
		layout: "centered",
	},
	decorators: [
		(Story) => (
			<QueryClientProvider client={queryClient}>
				<Story />
			</QueryClientProvider>
		),
	],
	tags: ["autodocs"],
} satisfies Meta<typeof WorkerMonitoring>;

export default meta;
type Story = StoryObj<typeof meta>;

export const WithWorkers: Story = {
	args: {
		workPoolName: "my-work-pool",
	},
	parameters: {
		msw: {
			handlers: [
				// Mock workers API with active workers
				{
					method: "POST",
					url: "/work_pools/my-work-pool/workers/filter",
					response: [
						{
							id: "worker1",
							name: "Worker 1",
							last_heartbeat_time: "2024-01-15T10:30:00Z",
						},
						{
							id: "worker2",
							name: "Worker 2",
							last_heartbeat_time: "2024-01-15T10:25:00Z",
						},
					],
				},
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
				// Mock workers API with no workers
				{
					method: "POST",
					url: "/work_pools/empty-work-pool/workers/filter",
					response: [],
				},
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
				// Mock workers API with workers but no heartbeat times
				{
					method: "POST",
					url: "/work_pools/inactive-work-pool/workers/filter",
					response: [
						{
							id: "worker1",
							name: "Worker 1",
							last_heartbeat_time: null,
						},
					],
				},
			],
		},
	},
};
