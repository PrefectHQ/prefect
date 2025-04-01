import { createFakeLog } from "@/mocks";
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
		logs: Array.from({ length: 3 }, () => createFakeLog()),
	},
};
