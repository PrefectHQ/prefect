import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { createFakeTaskRunConcurrencyLimit } from "@/mocks";
import { routerDecorator, toastDecorator } from "@/storybook/utils";
import { TaskRunConcurrencyLimitsDataTable } from "./task-run-concurrency-limits-data-table";

const MOCK_DATA = [
	createFakeTaskRunConcurrencyLimit(),
	createFakeTaskRunConcurrencyLimit(),
	createFakeTaskRunConcurrencyLimit(),
	createFakeTaskRunConcurrencyLimit(),
	createFakeTaskRunConcurrencyLimit(),
];

const meta = {
	title:
		"Components/Concurrency/TaskRunConcurrencyLimits/TaskRunConcurrencyLimitsDataTable",
	decorators: [routerDecorator, toastDecorator],
	component: TaskRunConcurrencyLimitsDataTable,
	args: {
		data: MOCK_DATA,
		onDeleteRow: fn(),
		onResetRow: fn(),
		onSearchChange: fn(),
		searchValue: "",
		onClearSearch: fn(),
		showFilteredEmptyState: false,
		pageCount: 1,
		pagination: { pageIndex: 0, pageSize: 10 },
		onPaginationChange: fn(),
	},
} satisfies Meta<typeof TaskRunConcurrencyLimitsDataTable>;
export default meta;

export const story: StoryObj = {
	name: "TaskRunConcurrencyLimitsDataTable",
};
