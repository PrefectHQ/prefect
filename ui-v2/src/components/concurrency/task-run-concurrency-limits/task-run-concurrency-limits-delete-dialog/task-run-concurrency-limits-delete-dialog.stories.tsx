import {
	createFakeTaskRunConcurrencyLimit,
	reactQueryDecorator,
} from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { TaskRunConcurrencyLimitsDeleteDialog } from "./task-run-concurrency-limits-delete-dialog";

const meta = {
	title:
		"Components/Concurrency/TaskRunConcurrencyLimits/TaskRunConcurrencyLimitsDeleteDialog",
	component: TaskRunConcurrencyLimitsDeleteDialog,
	decorators: [reactQueryDecorator],
	args: {
		data: createFakeTaskRunConcurrencyLimit(),
		onOpenChange: () => {},
		onDelete: () => {},
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitsDeleteDialog>;

export default meta;

export const story: StoryObj = { name: "TaskRunConcurrencyLimitsDeleteDialog" };
