import type { Meta, StoryObj } from "@storybook/react";

import { CodeBanner } from "./code-banner";

const meta: Meta<typeof CodeBanner> = {
	title: "Components/CodeBanner",
	component: CodeBanner,
	parameters: {
		layout: "padded",
	},
	args: {
		command: 'prefect worker start --pool "default"',
		title: "Your work pool is almost ready!",
		subtitle: "Run this command to start.",
	},
};

export default meta;
type Story = StoryObj<typeof CodeBanner>;

export const Default: Story = {};

export const LongCommand: Story = {
	args: {
		command:
			'prefect worker start --pool "very-long-work-pool-name-that-demonstrates-responsive-behavior"',
		title: "Start your worker",
		subtitle: "Copy and run this command in your terminal.",
	},
};

export const AgentPool: Story = {
	args: {
		command: 'prefect agent start --pool "legacy-agent-pool"',
		title: "Agent pool detected",
		subtitle: "Use the agent command for legacy pools.",
	},
};

export const CustomStyling: Story = {
	args: {
		command: "prefect deploy",
		title: "Deploy your flow",
		subtitle: "Ready to deploy? Run this command.",
		className: "max-w-md",
	},
};
