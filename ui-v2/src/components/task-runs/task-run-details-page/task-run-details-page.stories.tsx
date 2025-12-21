import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import {
	createFakeArtifact,
	createFakeLog,
	createFakeState,
	createFakeTaskRun,
} from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { TaskRunDetailsPage } from ".";

type TaskRunDetailsTabOptions = "Logs" | "Artifacts" | "TaskInputs" | "Details";

const mockTaskRun = createFakeTaskRun({
	id: "task-run-1",
	name: "my-task-run",
	flow_run_id: "flow-run-1",
	flow_run_name: "my-flow-run",
	task_key: "my_task",
	state: createFakeState({
		type: "COMPLETED",
		name: "Completed",
	}),
	task_inputs: {
		x: [{ input_type: "parameter", name: "x" }],
		y: [{ input_type: "parameter", name: "y" }],
	},
	tags: ["production", "etl"],
});

const mockLogs = [
	createFakeLog({
		id: "log-1",
		message: "Task starting...",
		level: 20,
		task_run_id: "task-run-1",
		timestamp: new Date(Date.now() - 5000).toISOString(),
	}),
	createFakeLog({
		id: "log-2",
		message: "Processing data...",
		level: 20,
		task_run_id: "task-run-1",
		timestamp: new Date(Date.now() - 3000).toISOString(),
	}),
	createFakeLog({
		id: "log-3",
		message: "Task completed successfully",
		level: 20,
		task_run_id: "task-run-1",
		timestamp: new Date(Date.now() - 1000).toISOString(),
	}),
];

const mockArtifacts = [
	createFakeArtifact({
		id: "artifact-1",
		key: "results",
		type: "table",
		task_run_id: "task-run-1",
	}),
	createFakeArtifact({
		id: "artifact-2",
		key: "metrics",
		type: "markdown",
		task_run_id: "task-run-1",
	}),
];

const TaskRunDetailsPageWithState = ({
	taskRunId = mockTaskRun.id,
	initialTab = "Logs" as TaskRunDetailsTabOptions,
}: {
	taskRunId?: string;
	initialTab?: TaskRunDetailsTabOptions;
}) => {
	const [tab, setTab] = useState<TaskRunDetailsTabOptions>(initialTab);

	return (
		<TaskRunDetailsPage
			id={taskRunId}
			tab={tab}
			onTabChange={(newTab) => setTab(newTab)}
		/>
	);
};

const meta = {
	title: "Components/TaskRuns/TaskRunDetailsPage",
	component: TaskRunDetailsPageWithState,
	decorators: [reactQueryDecorator, routerDecorator, toastDecorator],
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/ui/task_runs/:id"), () => {
					return HttpResponse.json(mockTaskRun);
				}),
				http.post(buildApiUrl("/logs/filter"), () => {
					return HttpResponse.json(mockLogs);
				}),
				http.post(buildApiUrl("/artifacts/filter"), () => {
					return HttpResponse.json(mockArtifacts);
				}),
			],
		},
	},
} satisfies Meta<typeof TaskRunDetailsPageWithState>;

export default meta;

type Story = StoryObj<typeof TaskRunDetailsPageWithState>;

export const Default: Story = {
	name: "Default (Logs Tab)",
	render: () => <TaskRunDetailsPageWithState />,
};

export const ArtifactsTab: Story = {
	name: "Artifacts Tab",
	render: () => <TaskRunDetailsPageWithState initialTab="Artifacts" />,
};

export const TaskInputsTab: Story = {
	name: "Task Inputs Tab",
	render: () => <TaskRunDetailsPageWithState initialTab="TaskInputs" />,
};

const failedTaskRun = createFakeTaskRun({
	id: "task-run-failed",
	name: "failed-task-run",
	flow_run_id: "flow-run-1",
	flow_run_name: "my-flow-run",
	task_key: "my_task",
	state: createFakeState({
		type: "FAILED",
		name: "Failed",
	}),
	task_inputs: {
		x: [{ input_type: "parameter", name: "x" }],
	},
	tags: ["production"],
});

const failedLogs = [
	createFakeLog({
		id: "log-1",
		message: "Task starting...",
		level: 20,
		task_run_id: "task-run-failed",
		timestamp: new Date(Date.now() - 5000).toISOString(),
	}),
	createFakeLog({
		id: "log-2",
		message: "Error: Connection refused",
		level: 40,
		task_run_id: "task-run-failed",
		timestamp: new Date(Date.now() - 3000).toISOString(),
	}),
	createFakeLog({
		id: "log-3",
		message: "Task failed with exception",
		level: 40,
		task_run_id: "task-run-failed",
		timestamp: new Date(Date.now() - 1000).toISOString(),
	}),
];

export const FailedRun: Story = {
	name: "Failed Run",
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/ui/task_runs/:id"), () => {
					return HttpResponse.json(failedTaskRun);
				}),
				http.post(buildApiUrl("/logs/filter"), () => {
					return HttpResponse.json(failedLogs);
				}),
				http.post(buildApiUrl("/artifacts/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
	render: () => <TaskRunDetailsPageWithState taskRunId={failedTaskRun.id} />,
};

const runningTaskRun = createFakeTaskRun({
	id: "task-run-running",
	name: "running-task-run",
	flow_run_id: "flow-run-1",
	flow_run_name: "my-flow-run",
	task_key: "my_task",
	state: createFakeState({
		type: "RUNNING",
		name: "Running",
	}),
	task_inputs: {
		x: [{ input_type: "parameter", name: "x" }],
	},
	tags: ["development"],
});

const runningLogs = [
	createFakeLog({
		id: "log-1",
		message: "Task starting...",
		level: 20,
		task_run_id: "task-run-running",
		timestamp: new Date(Date.now() - 5000).toISOString(),
	}),
	createFakeLog({
		id: "log-2",
		message: "Processing batch 1 of 10...",
		level: 20,
		task_run_id: "task-run-running",
		timestamp: new Date(Date.now() - 3000).toISOString(),
	}),
];

export const RunningRun: Story = {
	name: "Running Run",
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/ui/task_runs/:id"), () => {
					return HttpResponse.json(runningTaskRun);
				}),
				http.post(buildApiUrl("/logs/filter"), () => {
					return HttpResponse.json(runningLogs);
				}),
				http.post(buildApiUrl("/artifacts/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
	render: () => <TaskRunDetailsPageWithState taskRunId={runningTaskRun.id} />,
};
