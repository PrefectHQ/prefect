import { createFakeLog, createFakeTaskRun } from "@/mocks";
import type { Meta, StoryObj } from "@storybook/react";
import { RunLogs } from ".";

export default {
	title: "UI/RunLogs",
	component: (args) => (
		<div>
			<RunLogs {...args} />
		</div>
	),
	parameters: {
		layout: "centered",
	},
} satisfies Meta<typeof RunLogs>;

type Story = StoryObj<typeof RunLogs>;

export const logs: Story = {
	name: "RunLogs",
	args: {
		logs: Array.from({ length: 7 }, () => createFakeLog()).sort((a, b) =>
			a.timestamp.localeCompare(b.timestamp),
		),
		taskRun: createFakeTaskRun(),
	},
};

export const noLogs: Story = {
	args: {
		logs: [],
		taskRun: createFakeTaskRun(),
	},
};
