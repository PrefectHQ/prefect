import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { createFakeGlobalConcurrencyLimit } from "@/mocks";
import { reactQueryDecorator, toastDecorator } from "@/storybook/utils";
import { Table as GlobalConcurrencyLimitsDataTable } from "./global-concurrency-limits-data-table";

const MOCK_DATA = [
	createFakeGlobalConcurrencyLimit(),
	createFakeGlobalConcurrencyLimit(),
	createFakeGlobalConcurrencyLimit(),
	createFakeGlobalConcurrencyLimit(),
	createFakeGlobalConcurrencyLimit(),
];

const meta = {
	title:
		"Components/Concurrency/GlobalConcurrencyLimits/GlobalConcurrencyLimitsDataTable",
	component: GlobalConcurrencyLimitsDataTable,
	decorators: [reactQueryDecorator, toastDecorator],
	args: {
		data: MOCK_DATA,
		currentCount: MOCK_DATA.length,
		pagination: { pageIndex: 0, pageSize: 10 },
		onPaginationChange: fn(),
		onDeleteRow: fn(),
		onEditRow: fn(),
		onResetRow: fn(),
		onSearchChange: fn(),
		searchValue: "",
		showFilteredEmptyState: false,
		onClearSearch: fn(),
	},
} satisfies Meta<typeof GlobalConcurrencyLimitsDataTable>;

export default meta;

export const Story: StoryObj = {
	name: "GlobalConcurrencyLimitsDataTable",
};
