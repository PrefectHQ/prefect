import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { TaskRunsSortFilter } from "./task-run-sort-filter";

const meta = {
	title: "Components/TaskRuns/TaskRunsSortFilter",
	component: TaskRunsSortFilter,
} satisfies Meta<typeof TaskRunsSortFilter>;

export default meta;
type Story = StoryObj<typeof TaskRunsSortFilter>;

export const Default: Story = {
	args: {
		value: undefined,
		onSelect: fn(),
	},
};

export const NewestToOldest: Story = {
	args: {
		value: "EXPECTED_START_TIME_DESC",
		onSelect: fn(),
	},
};

export const OldestToNewest: Story = {
	args: {
		value: "EXPECTED_START_TIME_ASC",
		onSelect: fn(),
	},
};

export const WithDefaultValue: Story = {
	args: {
		defaultValue: "EXPECTED_START_TIME_DESC",
		value: undefined,
		onSelect: fn(),
	},
};
