import type { Meta, StoryObj } from "@storybook/react";
import { PinDeploymentButton } from "./pin-deployment-button";

const meta: Meta<typeof PinDeploymentButton> = {
	title: "Components/Deployments/PinDeploymentButton",
	component: PinDeploymentButton,
	parameters: {
		docs: {
			description: {
				component:
					"Toggles whether a deployment is pinned. Pins are saved in the browser's localStorage, so they are not shared between browsers or users.",
			},
		},
	},
};

export default meta;
type Story = StoryObj<typeof PinDeploymentButton>;

export const Default: Story = {
	args: {
		deploymentId: "deployment-123",
	},
};
