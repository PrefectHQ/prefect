import type { Meta, StoryObj } from "@storybook/react";

import { TaskRunConcurrencyLimitsActionsMenu } from "./task-run-concurrency-limits-actions-menu";

const meta = {
	title: "Components/Concurrency/TaskRunConcurrencyLimitsActionsMenu",
	component: TaskRunConcurrencyLimitsActionsMenu,
	args: {
		id: "0",
		onDelete: () => {},
		onReset: () => {},
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitsActionsMenu>;

export default meta;

export const story: StoryObj = { name: "TaskRunConcurrencyLimitsActionsMenu" };
