import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { createFakeTaskRunConcurrencyLimit } from "@/mocks";
import { routerDecorator, toastDecorator } from "@/storybook/utils";
import { TaskRunConcurrencyLimitHeader } from "./task-run-concurrency-limit-header";

const meta = {
	title:
		"Components/Concurrency/TaskRunConcurrencyLimits/TaskRunConcurrencyLimitHeader",
	component: TaskRunConcurrencyLimitHeader,
	decorators: [routerDecorator, toastDecorator],
	args: {
		data: createFakeTaskRunConcurrencyLimit(),
		onDelete: fn(),
		onReset: fn(),
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitHeader>;

export default meta;

export const Story: StoryObj = {
	name: "TaskRunConcurrencyLimitHeader",
};
