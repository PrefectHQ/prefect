import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { createFakeTaskRunConcurrencyLimit } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { TaskRunConcurrencyLimitsResetDialog } from "./task-run-concurrency-limits-reset-dialog";

const meta = {
	title:
		"Components/Concurrency/TaskRunConcurrencyLimits/TaskRunConcurrencyLimitsResetDialog",
	component: TaskRunConcurrencyLimitsResetDialog,
	decorators: [reactQueryDecorator],
	args: {
		data: createFakeTaskRunConcurrencyLimit(),
		onOpenChange: fn(),
		onReset: fn(),
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitsResetDialog>;

export default meta;

export const story: StoryObj = { name: "TaskRunConcurrencyLimitsResetDialog" };
