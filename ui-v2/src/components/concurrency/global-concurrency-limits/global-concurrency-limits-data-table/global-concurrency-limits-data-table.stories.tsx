import {
	createFakeGlobalConcurrencyLimit,
	reactQueryDecorator,
} from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
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
	decorators: [reactQueryDecorator],
	args: {
		data: MOCK_DATA,
		onDeleteRow: () => {},
		onEditRow: () => {},
		onSearchChange: () => {},
		searchValue: "",
	},
} satisfies Meta<typeof GlobalConcurrencyLimitsDataTable>;

export default meta;

export const Story: StoryObj = {
	name: "GlobalConcurrencyLimitsDataTable",
};
