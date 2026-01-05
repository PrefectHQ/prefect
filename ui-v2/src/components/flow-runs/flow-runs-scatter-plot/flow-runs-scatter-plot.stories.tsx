import { randPastDate } from "@ngneat/falso";
import type { Meta, StoryObj } from "@storybook/react";
import type { ComponentProps } from "react";
import {
	createFakeSimpleFlowRuns,
	createFakeSimpleFlowRunsMultiDay,
} from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunsScatterPlot } from ".";

export default {
	title: "Components/FlowRuns/FlowRunsScatterPlot",
	component: FlowRunsScatterPlot,
	parameters: {
		layout: "centered",
	},
	args: {
		history: createFakeSimpleFlowRuns(50),
		startDate: randPastDate({ years: 0.1 }),
		endDate: new Date(),
	},
	decorators: [reactQueryDecorator, routerDecorator],
	render: function Render(args: ComponentProps<typeof FlowRunsScatterPlot>) {
		// Wrap in a container with explicit width to ensure ResponsiveContainer can measure
		// The component uses "hidden md:block" so we need a wide enough container
		return (
			<div className="w-[900px]">
				<FlowRunsScatterPlot {...args} />
			</div>
		);
	},
} satisfies Meta<typeof FlowRunsScatterPlot>;

type Story = StoryObj<typeof FlowRunsScatterPlot>;

export const Randomized: Story = {
	args: {
		startDate: randPastDate({ years: 0.1 }),
		endDate: new Date(),
		history: createFakeSimpleFlowRuns(50),
	},
};

export const Empty: Story = {
	args: {
		startDate: randPastDate(),
		endDate: new Date(),
		history: [],
	},
};

export const FewDataPoints: Story = {
	args: {
		startDate: randPastDate({ years: 0.1 }),
		endDate: new Date(),
		history: createFakeSimpleFlowRuns(5),
	},
};

/**
 * Multi-day story to test x-axis formatting when the time range spans multiple days.
 * Day boundaries (midnight) should show the date (e.g., "Mon 15") while other ticks show time.
 */
export const MultiDay: Story = {
	args: {
		startDate: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000), // 3 days ago
		endDate: new Date(),
		history: createFakeSimpleFlowRunsMultiDay(30, 3),
	},
};

/**
 * Week-long story to test x-axis formatting over a longer time range.
 */
export const WeekLong: Story = {
	args: {
		startDate: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000), // 7 days ago
		endDate: new Date(),
		history: createFakeSimpleFlowRunsMultiDay(50, 7),
	},
};
