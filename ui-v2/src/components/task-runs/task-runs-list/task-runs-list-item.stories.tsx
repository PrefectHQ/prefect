import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import {
	createFakeFlow,
	createFakeFlowRun,
	createFakeState,
	createFakeTaskRun,
} from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { TaskRunsListItem } from "./task-runs-list-item";

const meta = {
	title: "Components/TaskRuns/TaskRunsListItem",
	component: TaskRunsListItem,
	decorators: [routerDecorator, reactQueryDecorator],
} satisfies Meta<typeof TaskRunsListItem>;

export default meta;
type Story = StoryObj<typeof TaskRunsListItem>;

const defaultTaskRun = createFakeTaskRun({
	id: "task-run-1",
	name: "my-task-run",
	tags: ["production", "etl"],
	total_run_time: 300,
	estimated_run_time: 300,
	start_time: "2024-01-01T10:00:00Z",
	end_time: "2024-01-01T10:05:00Z",
});

const defaultFlow = createFakeFlow({
	id: "flow-1",
	name: "my-flow",
});

const defaultFlowRun = createFakeFlowRun({
	id: "flow-run-1",
	name: "my-flow-run",
	flow_id: "flow-1",
});

export const Default: Story = {
	args: {
		taskRun: defaultTaskRun,
	},
};

export const WithBreadcrumbs: Story = {
	args: {
		taskRun: defaultTaskRun,
		flow: defaultFlow,
		flowRun: defaultFlowRun,
	},
};

export const Selectable: Story = {
	args: {
		taskRun: defaultTaskRun,
		flow: defaultFlow,
		flowRun: defaultFlowRun,
		checked: false,
		onCheckedChange: fn(),
	},
};

export const Selected: Story = {
	args: {
		taskRun: defaultTaskRun,
		flow: defaultFlow,
		flowRun: defaultFlowRun,
		checked: true,
		onCheckedChange: fn(),
	},
};

export const CompletedState: Story = {
	args: {
		taskRun: createFakeTaskRun({
			state: createFakeState({ type: "COMPLETED", name: "Completed" }),
			state_type: "COMPLETED",
			state_name: "Completed",
		}),
	},
};

export const FailedState: Story = {
	args: {
		taskRun: createFakeTaskRun({
			state: createFakeState({
				type: "FAILED",
				name: "Failed",
				message: "Task execution failed",
			}),
			state_type: "FAILED",
			state_name: "Failed",
		}),
	},
};

export const RunningState: Story = {
	args: {
		taskRun: createFakeTaskRun({
			state: createFakeState({ type: "RUNNING", name: "Running" }),
			state_type: "RUNNING",
			state_name: "Running",
			end_time: null,
			total_run_time: 0,
			estimated_run_time: 0,
		}),
	},
};

export const ScheduledState: Story = {
	args: {
		taskRun: createFakeTaskRun({
			state: createFakeState({ type: "SCHEDULED", name: "Scheduled" }),
			state_type: "SCHEDULED",
			state_name: "Scheduled",
			start_time: null,
			end_time: null,
			total_run_time: 0,
			estimated_run_time: 0,
		}),
	},
};

export const CrashedState: Story = {
	args: {
		taskRun: createFakeTaskRun({
			state: createFakeState({
				type: "CRASHED",
				name: "Crashed",
				message: "Process terminated unexpectedly",
			}),
			state_type: "CRASHED",
			state_name: "Crashed",
		}),
	},
};

export const CancelledState: Story = {
	args: {
		taskRun: createFakeTaskRun({
			state: createFakeState({
				type: "CANCELLED",
				name: "Cancelled",
				message: "Cancelled by user",
			}),
			state_type: "CANCELLED",
			state_name: "Cancelled",
		}),
	},
};

export const PendingState: Story = {
	args: {
		taskRun: createFakeTaskRun({
			state: createFakeState({ type: "PENDING", name: "Pending" }),
			state_type: "PENDING",
			state_name: "Pending",
			start_time: null,
			end_time: null,
			total_run_time: 0,
			estimated_run_time: 0,
		}),
	},
};

export const WithManyTags: Story = {
	args: {
		taskRun: createFakeTaskRun({
			tags: ["production", "etl", "daily", "critical", "data-pipeline"],
		}),
	},
};

export const NoTags: Story = {
	args: {
		taskRun: createFakeTaskRun({
			tags: [],
		}),
	},
};

export const LongDuration: Story = {
	args: {
		taskRun: createFakeTaskRun({
			total_run_time: 7265,
			estimated_run_time: 7265,
		}),
	},
};

export const NoStartTime: Story = {
	args: {
		taskRun: createFakeTaskRun({
			start_time: null,
			expected_start_time: null,
			state: createFakeState({ type: "PENDING", name: "Pending" }),
			state_type: "PENDING",
			state_name: "Pending",
		}),
	},
};
