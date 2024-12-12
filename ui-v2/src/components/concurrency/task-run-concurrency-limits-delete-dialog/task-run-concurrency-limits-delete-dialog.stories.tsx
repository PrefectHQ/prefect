import { reactQueryDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { TaskRunConcurrencyLimitsDeleteDialog } from "./task-run-concurrency-limits-delete-dialog";

const MOCK_DATA = {
	id: "0",
	created: "2021-01-01T00:00:00Z",
	updated: "2021-01-01T00:00:00Z",
	tag: "my tag 0",
	concurrency_limit: 1,
	active_slots: ["id-0"],
};

const meta = {
	title: "Components/Concurrency/TaskRunConcurrencyLimitsDeleteDialog",
	component: TaskRunConcurrencyLimitsDeleteDialog,
	decorators: [reactQueryDecorator],
	args: {
		data: MOCK_DATA,
		onOpenChange: () => {},
		onDelete: () => {},
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitsDeleteDialog>;

export default meta;

export const story: StoryObj = { name: "TaskRunConcurrencyLimitsDeleteDialog" };
