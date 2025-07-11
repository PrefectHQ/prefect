import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { reactQueryDecorator } from "@/storybook/utils";
import { TaskRunConcurrencyLimitsCreateDialog } from "./task-run-concurrency-limits-create-dialog";

const meta = {
	title:
		"Components/Concurrency/TaskRunConcurrencyLimits/TaskRunConcurrencyLimitsCreateDialog",
	component: TaskRunConcurrencyLimitsCreateDialog,
	decorators: [reactQueryDecorator],
	args: {
		onOpenChange: fn(),
		onSubmit: fn(),
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitsCreateDialog>;

export default meta;

export const Story: StoryObj = {
	name: "TaskRunConcurrencyLimitsCreateDialog",
};
