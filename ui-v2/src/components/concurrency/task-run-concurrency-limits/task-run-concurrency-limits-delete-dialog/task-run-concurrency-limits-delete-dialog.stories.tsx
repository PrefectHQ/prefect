import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { createFakeTaskRunConcurrencyLimit } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { TaskRunConcurrencyLimitsDeleteDialog } from "./task-run-concurrency-limits-delete-dialog";

const meta = {
	title:
		"Components/Concurrency/TaskRunConcurrencyLimits/TaskRunConcurrencyLimitsDeleteDialog",
	component: TaskRunConcurrencyLimitsDeleteDialog,
	decorators: [reactQueryDecorator],
	args: {
		data: createFakeTaskRunConcurrencyLimit(),
		onOpenChange: fn(),
		onDelete: fn(),
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitsDeleteDialog>;

export default meta;

export const story: StoryObj = { name: "TaskRunConcurrencyLimitsDeleteDialog" };
