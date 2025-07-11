import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import type { components } from "@/api/prefect";
import { createFakeLog, createFakeTaskRun } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { TaskRunLogs } from ".";

const MOCK_TASK_RUN_WITH_LOGS = createFakeTaskRun();
const MOCK_TASK_RUN_WITHOUT_LOGS = createFakeTaskRun();
const MOCK_TASK_RUN_WITH_INFINITE_LOGS = createFakeTaskRun();
// Create a range of logs with different levels
const ALL_MOCK_LOGS = [
	createFakeLog({
		level: 50,
		message: "Critical error in task",
		task_run_id: MOCK_TASK_RUN_WITH_LOGS.id,
	}),
	createFakeLog({
		level: 40,
		message: "Error processing data",
		task_run_id: MOCK_TASK_RUN_WITH_LOGS.id,
	}),
	createFakeLog({
		level: 30,
		message: "Warning: slow performance",
		task_run_id: MOCK_TASK_RUN_WITH_LOGS.id,
	}),
	createFakeLog({
		level: 20,
		message: "Info: task started",
		task_run_id: MOCK_TASK_RUN_WITH_LOGS.id,
	}),
	createFakeLog({
		level: 20,
		message: "Info: processing data",
		task_run_id: MOCK_TASK_RUN_WITH_LOGS.id,
	}),
	createFakeLog({
		level: 10,
		message: "Debug: connection established",
		task_run_id: MOCK_TASK_RUN_WITH_LOGS.id,
	}),
	createFakeLog({
		level: 10,
		message: "Debug: cache hit",
		task_run_id: MOCK_TASK_RUN_WITH_LOGS.id,
	}),
].sort((a, b) => a.timestamp.localeCompare(b.timestamp));

type LogsFilterBody = components["schemas"]["Body_read_logs_logs_filter_post"];

export default {
	title: "Components/TaskRuns/TaskRunLogs",
	component: (args) => (
		<div className="w-screen h-screen">
			<TaskRunLogs {...args} />
		</div>
	),

	decorators: [reactQueryDecorator],
	parameters: {
		layout: "centered",
		msw: {
			handlers: [
				http.post(buildApiUrl("/logs/filter"), async ({ request }) => {
					const body = (await request.json()) as LogsFilterBody;

					// Filter logs by level if specified
					let filteredLogs = [...ALL_MOCK_LOGS];
					const minLevel = body.logs?.level?.ge_;
					if (typeof minLevel === "number") {
						filteredLogs = filteredLogs.filter((log) => log.level >= minLevel);
					}

					// Sort logs based on the sort parameter
					if (body.sort === "TIMESTAMP_DESC") {
						filteredLogs = filteredLogs.reverse();
					}

					return HttpResponse.json(filteredLogs);
				}),
			],
		},
	},
} satisfies Meta<typeof TaskRunLogs>;

type Story = StoryObj<typeof TaskRunLogs>;

export const Default: Story = {
	args: {
		taskRun: MOCK_TASK_RUN_WITH_LOGS,
	},
};

export const NoLogs: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/logs/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
	args: {
		taskRun: MOCK_TASK_RUN_WITHOUT_LOGS,
	},
};

export const Infinite: Story = {
	args: {
		taskRun: MOCK_TASK_RUN_WITH_INFINITE_LOGS,
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/logs/filter"), async ({ request }) => {
					const body = (await request.json()) as LogsFilterBody;
					return HttpResponse.json(
						Array.from({ length: body.limit as number }, createFakeLog).sort(
							(a, b) => a.timestamp.localeCompare(b.timestamp),
						),
					);
				}),
			],
		},
	},
};
