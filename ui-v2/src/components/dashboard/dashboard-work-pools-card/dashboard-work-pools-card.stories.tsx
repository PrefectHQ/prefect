import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { FlowRunActivityBarGraphTooltipProvider } from "@/components/ui/flow-run-activity-bar-graph";
import { createFakeFlowRun } from "@/mocks/create-fake-flow-run";
import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import { createFakeWorkPoolQueue } from "@/mocks/create-fake-work-pool-queue";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";

import { DashboardWorkPoolsCard } from "./dashboard-work-pools-card";

const flowRunActivityBarGraphTooltipDecorator = (
	Story: React.ComponentType,
) => (
	<FlowRunActivityBarGraphTooltipProvider>
		<Story />
	</FlowRunActivityBarGraphTooltipProvider>
);

const meta: Meta<typeof DashboardWorkPoolsCard> = {
	title: "Components/Dashboard/DashboardWorkPoolsCard",
	component: DashboardWorkPoolsCard,
	decorators: [
		toastDecorator,
		routerDecorator,
		reactQueryDecorator,
		flowRunActivityBarGraphTooltipDecorator,
	],
	parameters: {
		msw: {
			handlers: [
				// Mock work pools endpoint
				http.post(buildApiUrl("/work_pools/filter"), () => {
					const workPools = [
						createFakeWorkPool({
							name: "production-pool",
							is_paused: false,
							status: "READY",
						}),
						createFakeWorkPool({
							name: "staging-pool",
							is_paused: false,
							status: "READY",
						}),
						createFakeWorkPool({
							name: "paused-pool",
							is_paused: true,
							status: "PAUSED",
						}),
					];
					return HttpResponse.json(workPools);
				}),

				// Mock flow runs count endpoint
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(42);
				}),

				// Mock flow runs filter endpoint
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					const flowRuns = [
						createFakeFlowRun({
							state: { id: "1", name: "Completed", type: "COMPLETED" },
						}),
						createFakeFlowRun({
							state: { id: "2", name: "Completed", type: "COMPLETED" },
						}),
						createFakeFlowRun({
							state: { id: "3", name: "Completed", type: "COMPLETED" },
						}),
						createFakeFlowRun({
							state: { id: "4", name: "Failed", type: "FAILED" },
						}),
					];
					return HttpResponse.json(flowRuns);
				}),

				// Mock work pool queues endpoint
				http.post(buildApiUrl("/work_pools/*/queues/filter"), () => {
					const queues = [
						createFakeWorkPoolQueue({
							name: "default",
							is_paused: false,
							status: "READY",
						}),
						createFakeWorkPoolQueue({
							name: "urgent",
							is_paused: false,
							status: "READY",
						}),
					];
					return HttpResponse.json(queues);
				}),
			],
		},
	},
};

export default meta;
type Story = StoryObj<typeof meta>;

const mockFilter = {
	range: {
		start: "2024-01-01T00:00:00Z",
		end: "2024-01-02T00:00:00Z",
	},
	flow_runs: {
		start_time_before: new Date("2024-01-02T00:00:00Z"),
		start_time_after: new Date("2024-01-01T00:00:00Z"),
	},
};

export const Default: Story = {
	args: {
		filter: mockFilter,
	},
};

export const EmptyState: Story = {
	args: {
		filter: mockFilter,
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const OnlyPausedPools: Story = {
	args: {
		filter: mockFilter,
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					const workPools = [
						createFakeWorkPool({
							name: "paused-pool-1",
							is_paused: true,
							status: "PAUSED",
						}),
						createFakeWorkPool({
							name: "paused-pool-2",
							is_paused: true,
							status: "PAUSED",
						}),
					];
					return HttpResponse.json(workPools);
				}),
			],
		},
	},
};

export const ManyWorkPools: Story = {
	args: {
		filter: mockFilter,
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					const workPools = Array.from({ length: 5 }, (_, i) =>
						createFakeWorkPool({
							name: `work-pool-${i + 1}`,
							is_paused: false,
							status: "READY",
						}),
					);
					return HttpResponse.json(workPools);
				}),
				// Mock flow runs count endpoint
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(42);
				}),
				// Mock flow runs filter endpoint
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					const flowRuns = [
						createFakeFlowRun({
							state: { id: "1", name: "Completed", type: "COMPLETED" },
						}),
						createFakeFlowRun({
							state: { id: "2", name: "Completed", type: "COMPLETED" },
						}),
						createFakeFlowRun({
							state: { id: "3", name: "Completed", type: "COMPLETED" },
						}),
						createFakeFlowRun({
							state: { id: "4", name: "Failed", type: "FAILED" },
						}),
					];
					return HttpResponse.json(flowRuns);
				}),
				// Mock work pool queues endpoint
				http.post(buildApiUrl("/work_pools/*/queues/filter"), () => {
					const queues = [
						createFakeWorkPoolQueue({
							name: "default",
							is_paused: false,
							status: "READY",
						}),
						createFakeWorkPoolQueue({
							name: "urgent",
							is_paused: false,
							status: "READY",
						}),
					];
					return HttpResponse.json(queues);
				}),
			],
		},
	},
};

export const MixedStatus: Story = {
	args: {
		filter: mockFilter,
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					const workPools = [
						createFakeWorkPool({
							name: "healthy-pool",
							is_paused: false,
							status: "READY",
						}),
						createFakeWorkPool({
							name: "not-ready-pool",
							is_paused: false,
							status: "NOT_READY",
						}),
						createFakeWorkPool({
							name: "paused-pool",
							is_paused: true,
							status: "PAUSED",
						}),
					];
					return HttpResponse.json(workPools);
				}),
			],
		},
	},
};
