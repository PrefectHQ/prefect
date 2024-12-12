import { reactQueryDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { TaskRunConcurrencyLimitsResetDialog } from "./task-run-concurrency-limits-reset-dialog";

const MOCK_DATA = {
	id: "0",
	created: "2021-01-01T00:00:00Z",
	updated: "2021-01-01T00:00:00Z",
	tag: "my tag 0",
	concurrency_limit: 1,
	active_slots: ["id-0"],
};

const meta = {
	title: "Components/Concurrency/TaskRunConcurrencyLimitsResetDialog",
	component: TaskRunConcurrencyLimitsResetDialog,
	decorators: [reactQueryDecorator],
	args: {
		data: MOCK_DATA,
		onOpenChange: () => {},
		onReset: () => {},
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitsResetDialog>;

export default meta;

export const story: StoryObj = { name: "TaskRunConcurrencyLimitsResetDialog" };
