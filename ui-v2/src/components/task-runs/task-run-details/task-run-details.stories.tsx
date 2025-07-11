import { randUuid } from "@ngneat/falso";
import type { Meta, StoryObj } from "@storybook/react";
import { createFakeTaskRun } from "@/mocks";
import { TaskRunDetails } from "./task-run-details";

export default {
	title: "Components/TaskRuns/TaskRunDetails",
	component: TaskRunDetails,
	parameters: {
		layout: "centered",
	},
} satisfies Meta<typeof TaskRunDetails>;

type Story = StoryObj<typeof TaskRunDetails>;

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
