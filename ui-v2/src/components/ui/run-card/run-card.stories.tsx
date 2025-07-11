import type { Meta, StoryObj } from "@storybook/react";
import { createFakeFlow, createFakeFlowRun, createFakeTaskRun } from "@/mocks";
import { routerDecorator } from "@/storybook/utils";
import { RunCard } from "./run-card";

const meta: Meta<typeof RunCard> = {
	title: "UI/RunCard",
	decorators: [routerDecorator],
	component: RunCard,
};
export default meta;

type Story = StoryObj<typeof RunCard>;

export const FlowRun: Story = {
	args: {
		flow: createFakeFlow(),
		flowRun: createFakeFlowRun(),
	},
};

export const TaskRunInFlowRun: Story = {
	args: {
		flow: createFakeFlow(),
		flowRun: createFakeFlowRun(),
		taskRun: createFakeTaskRun(),
	},
};

export const TaskRunOnly: Story = {
	args: {
		taskRun: createFakeTaskRun(),
	},
};
