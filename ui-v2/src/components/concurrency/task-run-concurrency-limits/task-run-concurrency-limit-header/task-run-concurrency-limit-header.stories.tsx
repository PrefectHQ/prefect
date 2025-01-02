import {
	createFakeTaskRunConcurrencyLimit,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";

import { TaskRunConcurrencyLimitHeader } from "./task-run-concurrency-limit-header";

const meta = {
	title:
		"Components/Concurrency/TaskRunConcurrencyLimits/TaskRunConcurrencyLimitHeader",
	component: TaskRunConcurrencyLimitHeader,
	decorators: [routerDecorator, toastDecorator],
	args: {
		data: createFakeTaskRunConcurrencyLimit(),
		onDelete: () => {},
		onReset: () => {},
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitHeader>;

export default meta;

export const Story: StoryObj = {
	name: "TaskRunConcurrencyLimitHeader",
};
