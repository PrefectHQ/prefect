import type { Meta, StoryObj } from "@storybook/react";
import { LogLevelBadge } from ".";

export default {
	title: "UI/LogLevelBadge",
	component: () => (
		<div className="flex flex-row gap-2">
			<LogLevelBadge level={50} />
			<LogLevelBadge level={40} />
			<LogLevelBadge level={30} />
			<LogLevelBadge level={20} />
			<LogLevelBadge level={10} />
			<LogLevelBadge level={0} />
		</div>
	),
	parameters: {
		layout: "centered",
	},
} satisfies Meta<typeof LogLevelBadge>;

type Story = StoryObj<typeof LogLevelBadge>;

export const logs: Story = {
	name: "LogLevelBadge",
};
