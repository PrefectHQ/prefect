import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HttpResponse, http } from "msw";

import type { WorkPool } from "@/api/work-pools";

import { WorkPoolDetails } from "./work-pool-details";

const queryClient = new QueryClient();

const meta = {
	title: "Components/WorkPools/WorkPoolDetails",
	component: WorkPoolDetails,
	parameters: {
		layout: "padded",
	},
	decorators: [
		(Story) => (
			<QueryClientProvider client={queryClient}>
				<div className="max-w-4xl">
					<Story />
				</div>
			</QueryClientProvider>
		),
	],
	tags: ["autodocs"],
} satisfies Meta<typeof WorkPoolDetails>;

export default meta;
type Story = StoryObj<typeof meta>;

const mockWorkPool: WorkPool = {
	id: "work-pool-1",
	name: "production-docker-pool",
	description: "Production Docker work pool for running containerized flows",
	type: "docker",
	status: "READY",
	concurrency_limit: 50,
	created: "2024-01-15T10:00:00Z",
	updated: "2024-01-20T15:30:00Z",
	is_paused: false,
	base_job_template: {
		job_configuration: {
			image: "prefecthq/prefect:2.0.0",
			command: ["python", "-m", "prefect.engine"],
			env: {
				PREFECT_API_URL: "https://api.prefect.cloud",
				NODE_ENV: "production",
				LOG_LEVEL: "INFO",
			},
			resources: {
				cpu: "1000m",
				memory: "2Gi",
			},
		},
		variables: {
			image: {
				type: "string",
				default: "prefecthq/prefect:2.0.0",
				title: "Docker Image",
				description: "The Docker image to use for the job",
			},
			env: {
				type: "object",
				default: {},
				title: "Environment Variables",
				description: "Environment variables to set in the container",
			},
			resources: {
				type: "object",
				default: {},
				title: "Resource Limits",
				description: "CPU and memory resource limits",
			},
		},
	},
};

export const Default: Story = {
	args: {
		workPool: mockWorkPool,
	},
	parameters: {
		msw: {
			handlers: [
				http.post("/work_pools/production-docker-pool/workers/filter", () => {
					return HttpResponse.json([
						{
							id: "worker1",
							name: "Worker 1",
							created: "2024-01-20T15:00:00Z",
							updated: "2024-01-20T16:00:00Z",
							work_pool_id: "production-docker-pool",
							last_heartbeat_time: "2024-01-20T16:00:00Z",
							heartbeat_interval_seconds: 30,
							status: "ONLINE",
						},
						{
							id: "worker2",
							name: "Worker 2",
							created: "2024-01-20T15:00:00Z",
							updated: "2024-01-20T15:55:00Z",
							work_pool_id: "production-docker-pool",
							last_heartbeat_time: "2024-01-20T15:55:00Z",
							heartbeat_interval_seconds: 30,
							status: "ONLINE",
						},
					]);
				}),
			],
		},
	},
};

export const WithoutWorkers: Story = {
	args: {
		workPool: mockWorkPool,
	},
	parameters: {
		msw: {
			handlers: [
				http.post("/work_pools/production-docker-pool/workers/filter", () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const WithoutJobTemplate: Story = {
	args: {
		workPool: {
			...mockWorkPool,
			base_job_template: undefined,
		},
	},
	parameters: {
		msw: {
			handlers: [
				http.post("/work_pools/production-docker-pool/workers/filter", () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const PausedWorkPool: Story = {
	args: {
		workPool: {
			...mockWorkPool,
			status: "PAUSED",
			is_paused: true,
		},
	},
	parameters: {
		msw: {
			handlers: [
				http.post("/work_pools/production-docker-pool/workers/filter", () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const NotReadyWorkPool: Story = {
	args: {
		workPool: {
			...mockWorkPool,
			status: "NOT_READY",
			description: undefined,
			concurrency_limit: undefined,
		},
	},
	parameters: {
		msw: {
			handlers: [
				http.post("/work_pools/production-docker-pool/workers/filter", () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const AlternateLayout: Story = {
	args: {
		workPool: mockWorkPool,
		alternate: true,
	},
	parameters: {
		msw: {
			handlers: [
				http.post("/work_pools/production-docker-pool/workers/filter", () => {
					return HttpResponse.json([
						{
							id: "worker1",
							name: "Worker 1",
							created: "2024-01-20T15:00:00Z",
							updated: "2024-01-20T16:00:00Z",
							work_pool_id: "production-docker-pool",
							last_heartbeat_time: "2024-01-20T16:00:00Z",
							heartbeat_interval_seconds: 30,
							status: "ONLINE",
						},
					]);
				}),
			],
		},
	},
};

export const MinimalWorkPool: Story = {
	args: {
		workPool: {
			id: "minimal-pool",
			name: "minimal-pool",
			type: "process",
			status: "READY",
			created: "2024-01-15T10:00:00Z",
			updated: "2024-01-15T10:00:00Z",
			is_paused: false,
		},
	},
	parameters: {
		msw: {
			handlers: [
				http.post("/work_pools/minimal-pool/workers/filter", () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};
