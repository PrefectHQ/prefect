import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { DateRangeFilter } from "./date-range-filter";
import type { DateRangeUrlState } from "./date-range-url-state";

const meta: Meta<typeof DateRangeFilter> = {
	title: "Components/FlowRuns/DateRangeFilter",
	component: DateRangeFilter,
	parameters: {
		layout: "centered",
	},
	tags: ["autodocs"],
};

export default meta;
type Story = StoryObj<typeof DateRangeFilter>;

const DateRangeFilterWithState = ({
	initialValue = {},
}: {
	initialValue?: DateRangeUrlState;
}) => {
	const [value, setValue] = useState<DateRangeUrlState>(initialValue);
	return <DateRangeFilter value={value} onValueChange={setValue} />;
};

export const Default: Story = {
	render: () => <DateRangeFilterWithState />,
};

export const WithPast24Hours: Story = {
	render: () => (
		<DateRangeFilterWithState initialValue={{ range: "past-24-hours" }} />
	),
};

export const WithPast7Days: Story = {
	render: () => (
		<DateRangeFilterWithState initialValue={{ range: "past-7-days" }} />
	),
};

export const WithPast30Days: Story = {
	render: () => (
		<DateRangeFilterWithState initialValue={{ range: "past-30-days" }} />
	),
};

export const WithToday: Story = {
	render: () => <DateRangeFilterWithState initialValue={{ range: "today" }} />,
};

export const WithCustomRange: Story = {
	render: () => (
		<DateRangeFilterWithState
			initialValue={{
				start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
				end: new Date().toISOString(),
			}}
		/>
	),
};
