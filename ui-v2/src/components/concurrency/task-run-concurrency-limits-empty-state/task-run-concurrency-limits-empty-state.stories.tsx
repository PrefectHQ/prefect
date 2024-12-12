import type { Meta, StoryObj } from "@storybook/react";

import { TaskRunConcurrencyLimitsEmptyState } from "./task-run-concurrency-limits-empty-state";

const meta = {
	title: "Components/Concurrency/TaskRunConcurrencyLimitsEmptyState",
	component: TaskRunConcurrencyLimitsEmptyState,
	args: {
		onAdd: () => {},
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitsEmptyState>;

export default meta;

export const Story: StoryObj = {
	name: "TaskRunConcurrencyLimitsEmptyState",
};
