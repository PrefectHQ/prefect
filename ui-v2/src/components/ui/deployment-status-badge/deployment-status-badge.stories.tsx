import { DeploymentStatusBadge } from ".";
import type { Meta, StoryObj } from "@storybook/react";
import type { ComponentProps } from "react";

export default {
	title: "Components/UI/DeploymentStatusBadge",
	component: DeploymentStatusBadge,
	args: {
		status: "READY",
	},
	render: function Render(args: ComponentProps<typeof DeploymentStatusBadge>) {
		return <DeploymentStatusBadge {...args} />;
	},
} satisfies Meta<typeof DeploymentStatusBadge>;

type Story = StoryObj<typeof DeploymentStatusBadge>;

export const Ready: Story = {
	args: {
		status: "READY",
	},
};

export const NotReady: Story = {
	args: {
		status: "NOT_READY",
	},
};
