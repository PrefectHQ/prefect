import type { Meta, StoryObj } from "@storybook/react";
import type { ComponentProps } from "react";
import { FlowRunActivityBarChart } from ".";

import { createFakeFlowRunWithDeploymentAndFlow } from "@/mocks/create-fake-flow-run";
import { routerDecorator } from "@/storybook/utils";
import { faker } from "@faker-js/faker";

export default {
	title: "UI/FlowRunActivityBarChart",
	component: FlowRunActivityBarChart,
	parameters: {
		layout: "centered",
	},
	args: {
		enrichedFlowRuns: [],
		startDate: new Date(),
		endDate: new Date(),
		numberOfBars: 18,
	},
	decorators: [routerDecorator],
	render: function Render(
		args: ComponentProps<typeof FlowRunActivityBarChart>,
	) {
		return <FlowRunActivityBarChart {...args} className="h-96" />;
	},
} satisfies Meta<typeof FlowRunActivityBarChart>;

type Story = StoryObj<typeof FlowRunActivityBarChart>;

export const Randomized: Story = {
	args: {
		startDate: faker.date.past(),
		endDate: new Date(),
		enrichedFlowRuns: Array.from(
			{ length: 18 },
			createFakeFlowRunWithDeploymentAndFlow,
		),
	},
};
