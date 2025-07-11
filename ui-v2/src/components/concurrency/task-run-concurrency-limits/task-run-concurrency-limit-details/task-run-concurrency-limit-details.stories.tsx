import type { Meta, StoryObj } from "@storybook/react";
import { createFakeTaskRunConcurrencyLimit } from "@/mocks";

import { TaskRunConcurrencyLimitDetails } from "./task-run-concurrency-limit-details";

export default {
	component: TaskRunConcurrencyLimitDetails,
	title:
		"Components/Concurrency/TaskRunConcurrencyLimits/TaskRunConcurrencyLimitDetails",
	args: { data: createFakeTaskRunConcurrencyLimit() },
} satisfies Meta;

export const story: StoryObj = { name: "TaskRunConcurrencyLimitDetails" };
