import type { Meta, StoryObj } from "@storybook/react";
import { createFakeFlow, createFakeFlowRun, createFakeTaskRun } from "@/mocks";
import { routerDecorator } from "@/storybook/utils";

import { TaskRunConcurrencyLimitActiveTaskRuns } from "./task-run-concurrency-limit-active-task-runs";

const MOCK_DATA = [
	{
		flow: createFakeFlow(),
		flowRun: createFakeFlowRun(),
		taskRun: createFakeTaskRun(),
	},
	{
		flow: createFakeFlow(),
		flowRun: createFakeFlowRun(),
		taskRun: createFakeTaskRun({ tags: ["foo", "bar", "baz"] }),
	},
	{
		flow: createFakeFlow(),
		flowRun: createFakeFlowRun(),
		taskRun: createFakeTaskRun(),
	},
	{
		taskRun: createFakeTaskRun(),
	},
	{
		flow: createFakeFlow(),
		flowRun: createFakeFlowRun(),
		taskRun: createFakeTaskRun(),
	},
	{
		taskRun: createFakeTaskRun({ tags: ["foo", "bar", "baz"] }),
	},
];

const meta: Meta<typeof TaskRunConcurrencyLimitActiveTaskRuns> = {
	title:
		"Components/Concurrency/TaskRunConcurrencyLimits/TaskRunConcurrencyLimitActiveTaskRuns",
	component: TaskRunConcurrencyLimitActiveTaskRuns,
	decorators: [routerDecorator],
	args: { data: MOCK_DATA },
};
export default meta;

type Story = StoryObj<typeof TaskRunConcurrencyLimitActiveTaskRuns>;

export const story: Story = {
	name: "TaskRunConcurrencyLimitActiveTaskRuns",
};
