import type { Meta, StoryObj } from "@storybook/react";

import { routerDecorator } from "@/storybook/utils";

import { RunCard } from "./run-card";
import { MOCK_FLOW, MOCK_FLOW_RUN, MOCK_TASK_RUN } from "./stories-data";

const meta: Meta<typeof RunCard> = {
	title: "UI/RunCard",
	decorators: [routerDecorator],
	component: RunCard,
};
export default meta;

type Story = StoryObj<typeof RunCard>;

export const FlowRun: Story = {
	args: {
		flow: MOCK_FLOW,
		flowRun: MOCK_FLOW_RUN,
	},
};

export const TaskRun: Story = {
	args: {
		flow: MOCK_FLOW,
		flowRun: MOCK_FLOW_RUN,
		taskRun: MOCK_TASK_RUN,
	},
};
