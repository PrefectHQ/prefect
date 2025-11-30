import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { Component, type ReactNode } from "react";
import type { components } from "@/api/prefect";
import {
	createFakeDeployment,
	createFakeFlow,
	createFakeFlowRun,
} from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunsCard } from "./index";

type StateType = components["schemas"]["StateType"];

const MOCK_FLOWS = [
	createFakeFlow({ id: "flow-1", name: "ETL Pipeline" }),
	createFakeFlow({ id: "flow-2", name: "Data Sync" }),
	createFakeFlow({ id: "flow-3", name: "Report Generator" }),
];

const MOCK_DEPLOYMENTS = [
	createFakeDeployment({ id: "deployment-1", name: "Production ETL" }),
	createFakeDeployment({ id: "deployment-2", name: "Staging Sync" }),
	createFakeDeployment({ id: "deployment-3", name: "Daily Reports" }),
];

const now = new Date();
const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);

const STATE_TYPES: StateType[] = [
	"COMPLETED",
	"FAILED",
	"RUNNING",
	"SCHEDULED",
	"CANCELLED",
];

function generateRandomFlowRuns(count: number) {
	const startMs = sevenDaysAgo.getTime();
	const endMs = now.getTime();
	const timeRange = endMs - startMs;

	return Array.from({ length: count }, (_, i) => {
		const randomTimestamp = new Date(startMs + Math.random() * timeRange);
		const stateType = STATE_TYPES[i % STATE_TYPES.length];
		const flow = MOCK_FLOWS[i % MOCK_FLOWS.length];
		const deployment = MOCK_DEPLOYMENTS[i % MOCK_DEPLOYMENTS.length];

		const isScheduled = stateType === "SCHEDULED";
		const isRunning = stateType === "RUNNING";

		return createFakeFlowRun({
			id: `run-${i}`,
			name: `${stateType.toLowerCase()}-run-${i}`,
			flow_id: flow.id,
			deployment_id: deployment.id,
			state_type: stateType,
			state_name: stateType.charAt(0) + stateType.slice(1).toLowerCase(),
			state: {
				id: `state-${i}`,
				type: stateType,
				name: stateType.charAt(0) + stateType.slice(1).toLowerCase(),
			},
			start_time: isScheduled ? null : randomTimestamp.toISOString(),
			end_time:
				isScheduled || isRunning
					? null
					: new Date(randomTimestamp.getTime() + 15 * 60 * 1000).toISOString(),
			expected_start_time: isScheduled
				? new Date(
						now.getTime() + Math.random() * 24 * 60 * 60 * 1000,
					).toISOString()
				: null,
			total_run_time:
				isScheduled || isRunning ? 0 : Math.floor(Math.random() * 3600),
		});
	});
}

const MOCK_FLOW_RUNS = generateRandomFlowRuns(40);

class StoryErrorBoundary extends Component<
	{ children: ReactNode },
	{ hasError: boolean; error: Error | null }
> {
	constructor(props: { children: ReactNode }) {
		super(props);
		this.state = { hasError: false, error: null };
	}

	static getDerivedStateFromError(error: Error) {
		return { hasError: true, error };
	}

	render() {
		if (this.state.hasError) {
			return (
				<div className="rounded-lg border border-red-200 bg-red-50 p-4">
					<h3 className="text-sm font-medium text-red-800">
						Error loading flow runs
					</h3>
					<p className="mt-1 text-sm text-red-600">
						{this.state.error?.message || "An unexpected error occurred"}
					</p>
				</div>
			);
		}
		return this.props.children;
	}
}

const meta = {
	title: "Dashboard/FlowRunsCard",
	component: FlowRunsCard,
	decorators: [routerDecorator, reactQueryDecorator],
} satisfies Meta<typeof FlowRunsCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		filter: {
			startDate: sevenDaysAgo.toISOString(),
			endDate: now.toISOString(),
		},
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json(MOCK_FLOW_RUNS);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json(MOCK_FLOWS);
				}),
				http.post(buildApiUrl("/deployments/filter"), () => {
					return HttpResponse.json(MOCK_DEPLOYMENTS);
				}),
			],
		},
	},
};

export const Empty: Story = {
	args: {
		filter: {
			startDate: sevenDaysAgo.toISOString(),
			endDate: now.toISOString(),
		},
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json([]);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json([]);
				}),
				http.post(buildApiUrl("/deployments/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const WithError: Story = {
	args: {
		filter: {
			startDate: sevenDaysAgo.toISOString(),
			endDate: now.toISOString(),
		},
	},
	render: (args) => (
		<StoryErrorBoundary>
			<FlowRunsCard {...args} />
		</StoryErrorBoundary>
	),
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json(
						{ detail: "Internal server error" },
						{ status: 500 },
					);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json([]);
				}),
				http.post(buildApiUrl("/deployments/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};
