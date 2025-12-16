import { randPastDate } from "@ngneat/falso";
import type { Meta, StoryObj } from "@storybook/react";
import type { ComponentProps } from "react";
import { createFakeSimpleFlowRuns } from "@/mocks";
import { routerDecorator } from "@/storybook/utils";
import { FlowRunsScatterPlot } from ".";

export default {
	title: "Components/FlowRuns/FlowRunsScatterPlot",
	component: FlowRunsScatterPlot,
	parameters: {
		layout: "centered",
	},
	args: {
		history: [],
		startDate: undefined,
		endDate: undefined,
	},
	decorators: [routerDecorator],
	render: function Render(args: ComponentProps<typeof FlowRunsScatterPlot>) {
		return <FlowRunsScatterPlot {...args} />;
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
