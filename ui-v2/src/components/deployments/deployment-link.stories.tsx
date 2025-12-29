import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DeploymentLink } from "./deployment-link";

const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			retry: false,
		},
	},
});

const meta: Meta<typeof DeploymentLink> = {
	title: "Components/Deployments/DeploymentLink",
	component: DeploymentLink,
	decorators: [
		(Story) => (
			<QueryClientProvider client={queryClient}>
				<Story />
			</QueryClientProvider>
		),
	],
	parameters: {
		docs: {
			description: {
				component:
					"A link component that fetches and displays a deployment name with a Rocket icon, linking to the deployment detail page.",
			},
		},
	},
};

export default meta;
type Story = StoryObj<typeof DeploymentLink>;

export const Default: Story = {
	args: {
		deploymentId: "deployment-123",
	},
};
