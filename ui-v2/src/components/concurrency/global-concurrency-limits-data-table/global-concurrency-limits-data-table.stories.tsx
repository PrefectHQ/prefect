import { reactQueryDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { Table } from "./global-concurrency-limits-data-table";

const MOCK_DATA = [
	{
		id: "0",
		created: "2021-01-01T00:00:00Z",
		updated: "2021-01-01T00:00:00Z",
		active: false,
		name: "global concurrency limit 0",
		limit: 0,
		active_slots: 0,
		slot_decay_per_second: 0,
	},
];

const meta = {
	title: "Components/Concurrency/GlobalConcurrencyLimitsDataTable",
	component: Table,
	decorators: [reactQueryDecorator],
	args: {
		data: MOCK_DATA,
		onDeleteRow: () => {},
		onEditRow: () => {},
		onSearchChange: () => {},
		searchValue: "",
	},
} satisfies Meta<typeof Table>;

export default meta;

export const Story: StoryObj = {
	name: "GlobalConcurrencyLimitsDataTable",
};
