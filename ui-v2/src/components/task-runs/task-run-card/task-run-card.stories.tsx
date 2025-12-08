import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { createFakeTaskRun } from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { TaskRunCard } from "./task-run-card";

const MOCK_TASK_RUN_COMPLETED = createFakeTaskRun({
	id: "completed-task",
	name: "completed-task-run",
	state: {
		type: "COMPLETED",
		name: "Completed",
		id: "state-1",
		timestamp: new Date().toISOString(),
	},
	tags: ["production", "daily"],
	flow_run_name: "my-flow-run",
	flow_run_id: "flow-run-id",
});

const MOCK_TASK_RUN_FAILED = createFakeTaskRun({
	id: "failed-task",
	name: "failed-task-run",
	state: {
		type: "FAILED",
		name: "Failed",
		id: "state-2",
		timestamp: new Date().toISOString(),
	},
	tags: ["staging"],
	flow_run_name: "my-flow-run",
	flow_run_id: "flow-run-id",
});

const MOCK_TASK_RUN_RUNNING = createFakeTaskRun({
	id: "running-task",
	name: "running-task-run",
	state: {
		type: "RUNNING",
		name: "Running",
		id: "state-3",
		timestamp: new Date().toISOString(),
	},
	tags: [],
	flow_run_name: "my-flow-run",
	flow_run_id: "flow-run-id",
});

const MOCK_TASK_RUN_SCHEDULED = createFakeTaskRun({
	id: "scheduled-task",
	name: "scheduled-task-run",
	state: {
		type: "SCHEDULED",
		name: "Scheduled",
		id: "state-4",
		timestamp: new Date().toISOString(),
	},
	tags: ["tag1", "tag2", "tag3", "tag4"],
	flow_run_name: "my-flow-run",
	flow_run_id: "flow-run-id",
});

const meta = {
	title: "Components/TaskRuns/TaskRunCard",
	component: TaskRunCard,
	decorators: [routerDecorator, reactQueryDecorator],
} satisfies Meta<typeof TaskRunCard>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Completed: Story = {
	args: {
		taskRun: MOCK_TASK_RUN_COMPLETED,
	},
};

export const Failed: Story = {
	args: {
		taskRun: MOCK_TASK_RUN_FAILED,
	},
};

export const Running: Story = {
	args: {
		taskRun: MOCK_TASK_RUN_RUNNING,
	},
};

export const Scheduled: Story = {
	args: {
		taskRun: MOCK_TASK_RUN_SCHEDULED,
	},
};

export const WithCheckbox: Story = {
	render: () => {
		const [checked, setChecked] = useState(false);
		return (
			<TaskRunCard
				taskRun={MOCK_TASK_RUN_COMPLETED}
				checked={checked}
				onCheckedChange={setChecked}
			/>
		);
	},
};

export const AllStates: Story = {
	render: () => (
		<div className="flex flex-col gap-2">
			<TaskRunCard taskRun={MOCK_TASK_RUN_COMPLETED} />
			<TaskRunCard taskRun={MOCK_TASK_RUN_FAILED} />
			<TaskRunCard taskRun={MOCK_TASK_RUN_RUNNING} />
			<TaskRunCard taskRun={MOCK_TASK_RUN_SCHEDULED} />
		</div>
	),
};
