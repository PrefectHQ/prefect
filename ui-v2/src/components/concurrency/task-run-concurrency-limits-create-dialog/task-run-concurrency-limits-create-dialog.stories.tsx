import { reactQueryDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { TaskRunConcurrencyLimitsCreateDialog } from "./task-run-concurrency-limits-create-dialog";

const meta = {
	title: "Components/Concurrency/TaskRunConcurrencyLimitsCreateDialog",
	component: TaskRunConcurrencyLimitsCreateDialog,
	decorators: [reactQueryDecorator],
	args: {
		onOpenChange: () => {},
		onSubmit: () => {},
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitsCreateDialog>;

export default meta;

export const Story: StoryObj = {
	name: "TaskRunConcurrencyLimitsCreateDialog",
};
