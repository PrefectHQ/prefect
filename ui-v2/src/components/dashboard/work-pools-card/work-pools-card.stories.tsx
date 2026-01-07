import { randNumber } from "@ngneat/falso";
import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { delay, HttpResponse, http } from "msw";
import {
	createFakeDeployment,
	createFakeFlow,
	createFakeFlowRun,
	createFakeWorkPool,
	createFakeWorkPoolQueues,
	createFakeWorkPoolWorkers,
} from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { DashboardWorkPoolsCard } from "./work-pools-card";

const createMockHandlers = (
	workPools: ReturnType<typeof createFakeWorkPool>[],
	options?: {
		flowRunCount?: number;
		workerCount?: number;
		queueCount?: number;
	},
) => {
	const {
		flowRunCount = randNumber({ min: 5, max: 15 }),
		workerCount = randNumber({ min: 1, max: 5 }),
		queueCount = randNumber({ min: 2, max: 8 }),
	} = options ?? {};

	// Generate random mock data for each request
	const mockFlows = Array.from({ length: 3 }, () => createFakeFlow());
	const mockDeployments = mockFlows.map((flow) =>
		createFakeDeployment({ flow_id: flow.id }),
	);

	// Create realistic flow runs spread over the time range
	const now = Date.now();
	const oneDayAgo = now - 24 * 60 * 60 * 1000;
	const mockFlowRuns = Array.from({ length: flowRunCount }, () => {
		const randomDeployment =
			mockDeployments[Math.floor(Math.random() * mockDeployments.length)];
		const randomFlow = mockFlows.find((f) => f.id === randomDeployment.flow_id);

		return createFakeFlowRun({
			deployment_id: randomDeployment.id,
			flow_id: randomFlow?.id,
			start_time: new Date(
				oneDayAgo + Math.random() * (now - oneDayAgo),
			).toISOString(),
		});
	});

	return [
		// Work pools
		http.post(buildApiUrl("/work_pools/filter"), () => {
			return HttpResponse.json(workPools);
		}),
		// Work pool workers - return random workers
		http.post(buildApiUrl("/work_pools/:name/workers/filter"), () => {
			return HttpResponse.json(createFakeWorkPoolWorkers(workerCount));
		}),
		// Work pool queues - return random queues
		http.post(buildApiUrl("/work_pools/:name/queues/filter"), ({ params }) => {
			return HttpResponse.json(
				createFakeWorkPoolQueues(params.name as string, queueCount),
			);
		}),
		// Flow runs count - return different counts for different filter types
		http.post(buildApiUrl("/flow_runs/count"), async ({ request }) => {
			const body = (await request.json()) as Record<string, unknown>;
			const stateFilter = body.flow_runs as Record<string, unknown>;
			const stateType = stateFilter?.state as Record<string, unknown>;
			const stateTypeAny = stateType?.type as Record<string, string[]>;

			// Late runs
			if (
				stateFilter?.state &&
				(stateFilter.state as Record<string, unknown>).name
			) {
				return HttpResponse.json(randNumber({ min: 0, max: 5 }));
			}

			// Completed, Failed, Crashed filter
			if (stateTypeAny?.any_?.includes("COMPLETED")) {
				const completedCount = mockFlowRuns.filter((fr) =>
					["COMPLETED", "FAILED", "CRASHED"].includes(fr.state?.type as string),
				).length;
				return HttpResponse.json(completedCount);
			}

			// All runs
			return HttpResponse.json(mockFlowRuns.length);
		}),
		// Flow runs lateness
		http.post(buildApiUrl("/flow_runs/lateness"), () => {
			return HttpResponse.json(randNumber({ min: 30, max: 300 }));
		}),
		// Flow runs for bar chart
		http.post(buildApiUrl("/flow_runs/filter"), () => {
			return HttpResponse.json(mockFlowRuns);
		}),
		// Deployments for enrichment - return from pool of mock deployments
		http.get(buildApiUrl("/deployments/:id"), ({ params }) => {
			const deployment = mockDeployments.find((d) => d.id === params.id);
			return HttpResponse.json(deployment ?? mockDeployments[0]);
		}),
		// Flows for enrichment - return from pool of mock flows
		http.get(buildApiUrl("/flows/:id"), ({ params }) => {
			const flow = mockFlows.find((f) => f.id === params.id);
			return HttpResponse.json(flow ?? mockFlows[0]);
		}),
	];
};

const meta = {
	title: "Components/Dashboard/DashboardWorkPoolsCard",
	component: DashboardWorkPoolsCard,
	decorators: [reactQueryDecorator, routerDecorator],
	args: {
		filter: {
			startDate: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
			endDate: new Date().toISOString(),
		},
	},
	parameters: {
		msw: {
			handlers: createMockHandlers([
				createFakeWorkPool({
					name: "Production Pool",
					is_paused: false,
					status: "READY",
				}),
				createFakeWorkPool({
					name: "Staging Pool",
					is_paused: false,
					status: "READY",
				}),
				createFakeWorkPool({
					name: "Development Pool",
					is_paused: false,
					status: "NOT_READY",
				}),
			]),
		},
	},
} satisfies Meta<typeof DashboardWorkPoolsCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const SingleWorkPool: Story = {
	parameters: {
		msw: {
			handlers: createMockHandlers([
				createFakeWorkPool({
					name: "Production Pool",
					is_paused: false,
					status: "READY",
				}),
			]),
		},
	},
};

export const EmptyState: Story = {
	parameters: {
		msw: {
			handlers: createMockHandlers([
				createFakeWorkPool({
					name: "Paused Pool",
					is_paused: true,
				}),
			]),
		},
	},
};

export const MixedStatuses: Story = {
	parameters: {
		msw: {
			handlers: createMockHandlers([
				createFakeWorkPool({
					name: "Ready Pool",
					is_paused: false,
					status: "READY",
				}),
				createFakeWorkPool({
					name: "Not Ready Pool",
					is_paused: false,
					status: "NOT_READY",
				}),
				createFakeWorkPool({
					name: "Unknown Status Pool",
					is_paused: false,
					status: null,
				}),
			]),
		},
	},
};

export const NoWorkPools: Story = {
	parameters: {
		msw: {
			handlers: createMockHandlers([]),
		},
	},
};

export const NoFlowRuns: Story = {
	parameters: {
		msw: {
			handlers: createMockHandlers(
				[
					createFakeWorkPool({
						name: "Production Pool",
						is_paused: false,
						status: "READY",
					}),
				],
				{ flowRunCount: 0 },
			),
		},
	},
};

export const Loading: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), async () => {
					await delay("infinite");
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const WithError: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json(
						{ detail: "Internal server error" },
						{ status: 500 },
					);
				}),
			],
		},
	},
};
