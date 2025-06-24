import type { Meta, StoryObj } from "@storybook/react";

import { fn } from "storybook/test";
import { TaskRunConcurrencyLimitsEmptyState } from "./task-run-concurrency-limits-empty-state";

const meta = {
	title:
		"Components/Concurrency/TaskRunConcurrencyLimits/TaskRunConcurrencyLimitsEmptyState",
	component: TaskRunConcurrencyLimitsEmptyState,
	args: {
		onAdd: fn(),
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitsEmptyState>;

export default meta;

export const Story: StoryObj = {
	name: "TaskRunConcurrencyLimitsEmptyState",
};
