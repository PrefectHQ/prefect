import type { Meta, StoryObj } from "@storybook/react";
import { createFakeDeployment } from "@/mocks";
import { DeploymentIconText } from "./deployment-icon-text";

const meta: Meta<typeof DeploymentIconText> = {
	title: "Components/Deployments/DeploymentIconText",
	component: DeploymentIconText,
	parameters: {
		docs: {
			description: {
				component:
					"A component that displays a deployment name with a Rocket icon, linking to the deployment detail page.",
			},
		},
	},
};

export default meta;
type Story = StoryObj<typeof DeploymentIconText>;

export const Default: Story = {
	args: {
		deployment: createFakeDeployment({
			id: "deployment-123",
			name: "my-deployment",
		}),
	},
};
