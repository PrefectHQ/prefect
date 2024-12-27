import {
	createFakeTaskRunConcurrencyLimit,
	routerDecorator,
} from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { Table as TaskRunConcurrencyLimitsDataTable } from "./task-run-concurrency-limits-data-table";

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
