import { routerDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";

import { TaskRunConcurrencyLimitHeader } from "./task-run-concurrency-limit-header";

const MOCK_DATA = {
	id: "0",
	created: "2021-01-01T00:00:00Z",
	updated: "2021-01-01T00:00:00Z",
	tag: "my tag 0",
	concurrency_limit: 1,
	active_slots: ["id=0"],
};

const meta = {
	title: "Components/Concurrency/TaskRunConcurrencyLimitHeader",
	component: TaskRunConcurrencyLimitHeader,
	decorators: [routerDecorator],
	args: {
		data: MOCK_DATA,
		onDelete: () => {},
		onReset: () => {},
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitHeader>;

export default meta;

export const Story: StoryObj = {
	name: "TaskRunConcurrencyLimitHeader",
};
