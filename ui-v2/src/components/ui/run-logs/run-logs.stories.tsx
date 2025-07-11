import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { createFakeLog, createFakeTaskRun } from "@/mocks";

import { RunLogs } from ".";

export default {
	title: "UI/RunLogs",
	component: (args) => (
		<div className="w-screen h-screen">
			<RunLogs {...args} />
		</div>
	),
} satisfies Meta<typeof RunLogs>;

type Story = StoryObj<typeof RunLogs>;

export const logs: Story = {
	name: "RunLogs",
	args: {
		logs: Array.from({ length: 100 }, () => createFakeLog()).sort((a, b) =>
			a.timestamp.localeCompare(b.timestamp),
		),
		taskRun: createFakeTaskRun(),
		onBottomReached: fn(),
	},
};

export const noLogs: Story = {
	args: {
		logs: [],
		taskRun: createFakeTaskRun(),
		onBottomReached: fn(),
	},
};
