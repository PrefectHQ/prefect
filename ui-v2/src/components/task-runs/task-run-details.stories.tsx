import { createFakeTaskRun } from "@/mocks";
import { randUuid } from "@ngneat/falso";
import type { Meta, StoryObj } from "@storybook/react";
import { TaskRuns } from ".";

export default {
	title: "Task Runs/TaskRuns",
	component: TaskRuns,
	parameters: {
		layout: "centered",
	},
} satisfies Meta<typeof TaskRuns>;

type Story = StoryObj<typeof TaskRuns>;

export const Default: Story = {
	args: {
		taskRun: createFakeTaskRun(),
	},
};

export const WithTags: Story = {
	args: {
		taskRun: createFakeTaskRun({
			tags: ["production", "critical", "daily-etl", "high-priority"],
		}),
	},
};

export const WithTaskInputs: Story = {
	args: {
		taskRun: createFakeTaskRun({
			task_inputs: {
				name: [
					{
						input_type: "parameter",
						name: "data_source",
					},
					{
						input_type: "parameter",
						name: "table_name",
					},
					{
						input_type: "parameter",
						name: "limit",
					},
				],
				upstream_tasks: [
					{
						input_type: "task_run",
						id: randUuid(),
					},
					{
						input_type: "task_run",
						id: randUuid(),
					},
				],
			},
		}),
	},
};

export const Completed: Story = {
	args: {
		taskRun: createFakeTaskRun({
			state: {
				id: randUuid(),
				type: "COMPLETED",
				name: "Completed",
				timestamp: new Date().toISOString(),
				message: "Task run completed successfully",
				data: null,
				state_details: {
					flow_run_id: "12345",
					task_run_id: "67890",
					child_flow_run_id: null,
					scheduled_time: null,
					cache_key: null,
					cache_expiration: null,
					deferred: false,
					untrackable_result: false,
					pause_timeout: null,
					pause_reschedule: false,
					pause_key: null,
					run_input_keyset: null,
					refresh_cache: null,
					retriable: null,
					transition_id: null,
					task_parameters_id: null,
				},
			},
			state_type: "COMPLETED",
			state_name: "Completed",
		}),
	},
};

export const Failed: Story = {
	args: {
		taskRun: createFakeTaskRun({
			state: {
				id: randUuid(),
				type: "FAILED",
				name: "Failed",
				timestamp: new Date().toISOString(),
				message: "Task run failed with error: Connection refused",
				data: null,
				state_details: {
					flow_run_id: "12345",
					task_run_id: "67890",
					child_flow_run_id: null,
					scheduled_time: null,
					cache_key: null,
					cache_expiration: null,
					deferred: false,
					untrackable_result: false,
					pause_timeout: null,
					pause_reschedule: false,
					pause_key: null,
					run_input_keyset: null,
					refresh_cache: null,
					retriable: null,
					transition_id: null,
					task_parameters_id: null,
				},
			},
			state_type: "FAILED",
			state_name: "Failed",
		}),
	},
};
