import { routerDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { TaskRunConcurrencyLimitsDataTable } from "./task-run-concurrency-limits-data-table";

const MOCK_DATA = [
	{
		id: "0",
		created: "2021-01-01T00:00:00Z",
		updated: "2021-01-01T00:00:00Z",
		tag: "my tag 0",
		concurrency_limit: 1,
		active_slots: ["id-0"],
	},
];

const meta = {
	title: "Components/Concurrency/TaskRunConcurrencyLimitsDataTable",
	decorators: [routerDecorator],
	component: TaskRunConcurrencyLimitsDataTable,
	args: {
		data: MOCK_DATA,
		onDeleteRow: () => {},
		onResetRow: () => {},
		onSearchChange: () => {},
		searchValue: () => {},
	},
} satisfies Meta;
export default meta;

export const story: StoryObj = {
	name: "TaskRunConcurrencyLimitsDataTable",
};
