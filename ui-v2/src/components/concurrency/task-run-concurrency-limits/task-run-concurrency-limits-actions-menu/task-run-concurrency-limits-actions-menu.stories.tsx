import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { toastDecorator } from "@/storybook/utils";
import { TaskRunConcurrencyLimitsActionsMenu } from "./task-run-concurrency-limits-actions-menu";

const meta = {
	title:
		"Components/Concurrency/TaskRunConcurrencyLimits/TaskRunConcurrencyLimitsActionsMenu",
	component: TaskRunConcurrencyLimitsActionsMenu,
	decorators: [toastDecorator],
	args: {
		id: "0",
		onDelete: fn(),
		onReset: fn(),
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitsActionsMenu>;

export default meta;

export const story: StoryObj = { name: "TaskRunConcurrencyLimitsActionsMenu" };
