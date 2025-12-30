import type { Meta, StoryObj } from "@storybook/react";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import type { Deployment } from "@/api/deployments";
import { createFakeDeployment } from "@/mocks";
import { DeploymentIconText } from "./deployment-icon-text";

const createTestRouter = (deployment: Deployment) => {
	const rootRoute = createRootRoute({
		component: () => <DeploymentIconText deployment={deployment} />,
	});

	return createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
	});
};

const meta: Meta<typeof DeploymentIconText> = {
	title: "Components/Deployments/DeploymentIconText",
	component: DeploymentIconText,
	decorators: [
		(_Story, context) => {
			const deployment =
				context.args.deployment ??
				createFakeDeployment({
					id: "deployment-123",
					name: "my-deployment",
				});
			const router = createTestRouter(deployment);
			return <RouterProvider router={router} />;
		},
	],
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
