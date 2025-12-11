import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import {
	TaskRunsListItem,
	type TaskRunsListItemData,
} from "./task-runs-list-item";

const createMockStateDetails = () => ({
	deferred: false,
	untrackable_result: false,
	pause_reschedule: false,
});

const createMockEmpiricalPolicy = () => ({
	max_retries: 0,
	retry_delay_seconds: 0,
	retries: 0,
	retry_delay: 0,
	retry_jitter_factor: null,
	resuming: null,
});

const createMockTaskRun = (
	overrides: Partial<TaskRunsListItemData> = {},
): TaskRunsListItemData => ({
	id: "task-run-1",
	name: "my-task-run",
	flow_run_id: "flow-run-1",
	task_key: "task-key-1",
	dynamic_key: "0",
	cache_key: null,
	cache_expiration: null,
	task_version: null,
	empirical_policy: createMockEmpiricalPolicy(),
	tags: ["production", "etl"],
	state_id: "state-1",
	task_inputs: {},
	state_type: "COMPLETED",
	state_name: "Completed",
	run_count: 1,
	flow_run_run_count: 1,
	expected_start_time: "2024-01-01T10:00:00Z",
	next_scheduled_start_time: null,
	start_time: "2024-01-01T10:00:00Z",
	end_time: "2024-01-01T10:05:00Z",
	total_run_time: 300,
	estimated_run_time: 300,
	estimated_start_time_delta: 0,
	state: {
		id: "state-1",
		type: "COMPLETED",
		name: "Completed",
		timestamp: "2024-01-01T10:05:00Z",
		message: null,
		state_details: createMockStateDetails(),
		data: null,
	},
	created: "2024-01-01T09:00:00Z",
	updated: "2024-01-01T10:05:00Z",
	...overrides,
});

const createMockFlow = () => ({
	id: "flow-1",
	name: "my-flow",
	created: "2024-01-01T00:00:00Z",
	updated: "2024-01-01T00:00:00Z",
	tags: [],
});

const createMockFlowRun = () => ({
	id: "flow-run-1",
	name: "my-flow-run",
	flow_id: "flow-1",
	deployment_id: null,
	work_queue_name: null,
	work_pool_name: null,
	state_id: "state-1",
	state_type: "COMPLETED" as const,
	state_name: "Completed",
	state: {
		id: "state-1",
		type: "COMPLETED" as const,
		name: "Completed",
		timestamp: "2024-01-01T10:05:00Z",
		message: null,
		state_details: createMockStateDetails(),
		data: null,
	},
	created: "2024-01-01T09:00:00Z",
	updated: "2024-01-01T10:05:00Z",
	tags: [],
	parameters: {},
	idempotency_key: null,
	context: {},
	empirical_policy: createMockEmpiricalPolicy(),
	auto_scheduled: false,
	infrastructure_document_id: null,
	infrastructure_pid: null,
	job_variables: null,
	parent_task_run_id: null,
	run_count: 1,
	expected_start_time: "2024-01-01T10:00:00Z",
	next_scheduled_start_time: null,
	start_time: "2024-01-01T10:00:00Z",
	end_time: "2024-01-01T10:05:00Z",
	total_run_time: 300,
	estimated_run_time: 300,
	estimated_start_time_delta: 0,
});

const meta = {
	title: "Components/TaskRuns/TaskRunsListItem",
	component: TaskRunsListItem,
	decorators: [routerDecorator, reactQueryDecorator],
} satisfies Meta<typeof TaskRunsListItem>;

export default meta;
type Story = StoryObj<typeof TaskRunsListItem>;

export const Default: Story = {
	args: {
		taskRun: createMockTaskRun(),
	},
};

export const WithBreadcrumbs: Story = {
	args: {
		taskRun: createMockTaskRun({
			flow: createMockFlow(),
			flowRun: createMockFlowRun(),
		}),
	},
};

export const Selectable: Story = {
	args: {
		taskRun: createMockTaskRun({
			flow: createMockFlow(),
			flowRun: createMockFlowRun(),
		}),
		checked: false,
		onCheckedChange: fn(),
	},
};

export const Selected: Story = {
	args: {
		taskRun: createMockTaskRun({
			flow: createMockFlow(),
			flowRun: createMockFlowRun(),
		}),
		checked: true,
		onCheckedChange: fn(),
	},
};

export const CompletedState: Story = {
	args: {
		taskRun: createMockTaskRun({
			state: {
				id: "state-1",
				type: "COMPLETED",
				name: "Completed",
				timestamp: "2024-01-01T10:05:00Z",
				message: null,
				state_details: createMockStateDetails(),
				data: null,
			},
			state_type: "COMPLETED",
		}),
	},
};

export const FailedState: Story = {
	args: {
		taskRun: createMockTaskRun({
			state: {
				id: "state-1",
				type: "FAILED",
				name: "Failed",
				timestamp: "2024-01-01T10:05:00Z",
				message: "Task execution failed",
				state_details: createMockStateDetails(),
				data: null,
			},
			state_type: "FAILED",
		}),
	},
};

export const RunningState: Story = {
	args: {
		taskRun: createMockTaskRun({
			state: {
				id: "state-1",
				type: "RUNNING",
				name: "Running",
				timestamp: "2024-01-01T10:00:00Z",
				message: null,
				state_details: createMockStateDetails(),
				data: null,
			},
			state_type: "RUNNING",
			end_time: null,
			total_run_time: 0,
			estimated_run_time: 0,
		}),
	},
};

export const ScheduledState: Story = {
	args: {
		taskRun: createMockTaskRun({
			state: {
				id: "state-1",
				type: "SCHEDULED",
				name: "Scheduled",
				timestamp: "2024-01-01T09:00:00Z",
				message: null,
				state_details: createMockStateDetails(),
				data: null,
			},
			state_type: "SCHEDULED",
			start_time: null,
			end_time: null,
			total_run_time: 0,
			estimated_run_time: 0,
		}),
	},
};

export const CrashedState: Story = {
	args: {
		taskRun: createMockTaskRun({
			state: {
				id: "state-1",
				type: "CRASHED",
				name: "Crashed",
				timestamp: "2024-01-01T10:05:00Z",
				message: "Process terminated unexpectedly",
				state_details: createMockStateDetails(),
				data: null,
			},
			state_type: "CRASHED",
		}),
	},
};

export const CancelledState: Story = {
	args: {
		taskRun: createMockTaskRun({
			state: {
				id: "state-1",
				type: "CANCELLED",
				name: "Cancelled",
				timestamp: "2024-01-01T10:02:00Z",
				message: "Cancelled by user",
				state_details: createMockStateDetails(),
				data: null,
			},
			state_type: "CANCELLED",
		}),
	},
};

export const PendingState: Story = {
	args: {
		taskRun: createMockTaskRun({
			state: {
				id: "state-1",
				type: "PENDING",
				name: "Pending",
				timestamp: "2024-01-01T09:55:00Z",
				message: null,
				state_details: createMockStateDetails(),
				data: null,
			},
			state_type: "PENDING",
			start_time: null,
			end_time: null,
			total_run_time: 0,
			estimated_run_time: 0,
		}),
	},
};

export const WithManyTags: Story = {
	args: {
		taskRun: createMockTaskRun({
			tags: ["production", "etl", "daily", "critical", "data-pipeline"],
		}),
	},
};

export const NoTags: Story = {
	args: {
		taskRun: createMockTaskRun({
			tags: [],
		}),
	},
};

export const LongDuration: Story = {
	args: {
		taskRun: createMockTaskRun({
			total_run_time: 7265,
			estimated_run_time: 7265,
		}),
	},
};

export const NoStartTime: Story = {
	args: {
		taskRun: createMockTaskRun({
			start_time: null,
			expected_start_time: null,
			state: {
				id: "state-1",
				type: "PENDING",
				name: "Pending",
				timestamp: "2024-01-01T09:55:00Z",
				message: null,
				state_details: createMockStateDetails(),
				data: null,
			},
			state_type: "PENDING",
		}),
	},
};
