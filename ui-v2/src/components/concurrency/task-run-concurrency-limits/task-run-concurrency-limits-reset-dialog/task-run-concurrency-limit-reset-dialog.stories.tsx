import {
	createFakeTaskRunConcurrencyLimit,
	reactQueryDecorator,
} from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { TaskRunConcurrencyLimitsResetDialog } from "./task-run-concurrency-limits-reset-dialog";

const meta = {
	title:
		"Components/Concurrency/TaskRunConcurrencyLimits/TaskRunConcurrencyLimitsResetDialog",
	component: TaskRunConcurrencyLimitsResetDialog,
	decorators: [reactQueryDecorator],
	args: {
		data: createFakeTaskRunConcurrencyLimit(),
		onOpenChange: () => {},
		onReset: () => {},
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitsResetDialog>;

export default meta;

export const story: StoryObj = { name: "TaskRunConcurrencyLimitsResetDialog" };
