import type { Meta, StoryObj } from "@storybook/react";

import { TaskRunConcurrencyLimitsHeader } from "./task-run-concurrency-limits-header";

const meta = {
	title: "Components/Concurrency/TaskRunConcurrencyLimitsHeader",
	component: TaskRunConcurrencyLimitsHeader,
	args: {
		onAdd: () => {},
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitsHeader>;

export default meta;

export const Story: StoryObj = {
	name: "TaskRunConcurrencyLimitsHeader",
};
