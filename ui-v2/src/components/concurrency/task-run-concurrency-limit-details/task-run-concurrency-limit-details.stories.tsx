import { TaskRunConcurrencyLimitDetails } from "./task-run-concurrency-limit-details";

import type { Meta, StoryObj } from "@storybook/react";

const MOCK_DATA = {
	id: "0",
	created: "2021-01-01T00:00:00Z",
	updated: "2021-01-01T00:00:00Z",
	tag: "my tag 0",
	concurrency_limit: 1,
	active_slots: ["id-0"],
};

export default {
	component: TaskRunConcurrencyLimitDetails,
	title: "Components/Concurrency/TaskRunConcurrencyLimitDetails",
	args: { data: MOCK_DATA },
} satisfies Meta;

export const story: StoryObj = { name: "TaskRunConcurrencyLimitDetails" };
