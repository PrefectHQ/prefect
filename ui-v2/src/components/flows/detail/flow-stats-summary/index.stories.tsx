import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import type { components } from "@/api/prefect";
import { createFakeFlow, createFakeFlowRun, createFakeTaskRun } from "@/mocks";
import { createFakeState } from "@/mocks/create-fake-state";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowStatsSummary } from "./index";

type StateType = components["schemas"]["StateType"];

const MOCK_FLOW = createFakeFlow({ id: "flow-1", name: "ETL Pipeline" });

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

		const isScheduled = stateType === "SCHEDULED";
		const isRunning = stateType === "RUNNING";

		return createFakeFlowRun({
			id: `run-${i}`,
			name: `${stateType.toLowerCase()}-run-${i}`,
			flow_id: MOCK_FLOW.id,
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
			total_run_time:
				isScheduled || isRunning ? 0 : Math.floor(Math.random() * 3600),
		});
	});
}

function generateTaskRuns(count: number) {
	const startMs = sevenDaysAgo.getTime();
	const endMs = now.getTime();
	const timeRange = endMs - startMs;

	return Array.from({ length: count }, (_, i) => {
		const randomTimestamp = new Date(startMs + Math.random() * timeRange);
		const isCompleted = i % 5 !== 0;
		const stateType = isCompleted ? "COMPLETED" : "FAILED";

		return createFakeTaskRun({
			id: `task-run-${i}`,
			name: `task-${i}`,
			flow_run_id: `run-${i % 10}`,
			state_type: stateType,
			state_name: stateType.charAt(0) + stateType.slice(1).toLowerCase(),
			state: createFakeState({
				type: stateType,
				name: stateType.charAt(0) + stateType.slice(1).toLowerCase(),
			}),
			start_time: randomTimestamp.toISOString(),
			end_time: new Date(
				randomTimestamp.getTime() + Math.random() * 60000,
			).toISOString(),
		});
	});
}

function generateTaskRunsHistory() {
	const intervals = 20;
	const intervalMs = (7 * 24 * 60 * 60 * 1000) / intervals;

	return Array.from({ length: intervals }, (_, i) => {
		const intervalStart = new Date(
			sevenDaysAgo.getTime() + i * intervalMs,
		).toISOString();
		const intervalEnd = new Date(
			sevenDaysAgo.getTime() + (i + 1) * intervalMs,
		).toISOString();

		const completedCount = Math.floor(Math.random() * 10) + 1;
		const failedCount = Math.random() > 0.7 ? Math.floor(Math.random() * 3) : 0;

		return {
			interval_start: intervalStart,
			interval_end: intervalEnd,
			states: [
				{
					state_type: "COMPLETED",
					state_name: "Completed",
					count_runs: completedCount,
				},
				...(failedCount > 0
					? [
							{
								state_type: "FAILED",
								state_name: "Failed",
								count_runs: failedCount,
							},
						]
					: []),
			],
		};
	});
}

const MOCK_FLOW_RUNS = generateRandomFlowRuns(38);
const MOCK_TASK_RUNS = generateTaskRuns(50);
const MOCK_TASK_RUNS_HISTORY = generateTaskRunsHistory();

const meta = {
	title: "Flows/FlowStatsSummary",
	component: FlowStatsSummary,
	decorators: [routerDecorator, reactQueryDecorator],
} satisfies Meta<typeof FlowStatsSummary>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		flowId: MOCK_FLOW.id,
		flow: MOCK_FLOW,
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json(MOCK_FLOW_RUNS);
				}),
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(MOCK_FLOW_RUNS.length);
				}),
				http.post(buildApiUrl("/task_runs/count"), () => {
					return HttpResponse.json(MOCK_TASK_RUNS.length);
				}),
				http.post(buildApiUrl("/task_runs/history"), () => {
					return HttpResponse.json(MOCK_TASK_RUNS_HISTORY);
				}),
			],
		},
	},
};

export const Empty: Story = {
	args: {
		flowId: MOCK_FLOW.id,
		flow: MOCK_FLOW,
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json([]);
				}),
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(0);
				}),
				http.post(buildApiUrl("/task_runs/count"), () => {
					return HttpResponse.json(0);
				}),
				http.post(buildApiUrl("/task_runs/history"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const ManyFlowRuns: Story = {
	args: {
		flowId: MOCK_FLOW.id,
		flow: MOCK_FLOW,
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json(generateRandomFlowRuns(60));
				}),
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(150);
				}),
				http.post(buildApiUrl("/task_runs/count"), () => {
					return HttpResponse.json(500);
				}),
				http.post(buildApiUrl("/task_runs/history"), () => {
					return HttpResponse.json(MOCK_TASK_RUNS_HISTORY);
				}),
			],
		},
	},
};

export const NoFailedTaskRuns: Story = {
	args: {
		flowId: MOCK_FLOW.id,
		flow: MOCK_FLOW,
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), () => {
					return HttpResponse.json(MOCK_FLOW_RUNS);
				}),
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(MOCK_FLOW_RUNS.length);
				}),
				http.post(buildApiUrl("/task_runs/count"), () => {
					return HttpResponse.json(40);
				}),
				http.post(buildApiUrl("/task_runs/history"), () => {
					const historyWithNoFailed = MOCK_TASK_RUNS_HISTORY.map(
						(interval) => ({
							...interval,
							states: interval.states.filter((s) => s.state_type !== "FAILED"),
						}),
					);
					return HttpResponse.json(historyWithNoFailed);
				}),
			],
		},
	},
};
