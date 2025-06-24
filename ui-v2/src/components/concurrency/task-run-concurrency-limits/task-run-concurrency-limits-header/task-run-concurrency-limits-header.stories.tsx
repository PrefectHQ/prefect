import type { Meta, StoryObj } from "@storybook/react";

import { fn } from "storybook/test";
import { TaskRunConcurrencyLimitsHeader } from "./task-run-concurrency-limits-header";

const meta = {
	title:
		"Components/Concurrency/TaskRunConcurrencyLimits/TaskRunConcurrencyLimitsHeader",
	component: TaskRunConcurrencyLimitsHeader,
	args: { onAdd: fn() },
} satisfies Meta<typeof TaskRunConcurrencyLimitsHeader>;

export default meta;

export const Story: StoryObj = {
	name: "TaskRunConcurrencyLimitsHeader",
};
