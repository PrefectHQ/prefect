import type { Meta, StoryObj } from "@storybook/react";
import { createFakeDeployment } from "@/mocks";
import { DeploymentDescription } from "./deployment-description";

const meta = {
	title: "Components/Deployments/DeploymentDescription",
	component: DeploymentDescription,
} satisfies Meta<typeof DeploymentDescription>;

export default meta;
type Story = StoryObj<typeof DeploymentDescription>;

export const WithDescription: Story = {
	name: "With Description",
	args: {
		deployment: createFakeDeployment({
			description:
				"# My Deployment\n\nThis deployment runs a daily ETL pipeline that extracts data from the source database, transforms it, and loads it into the data warehouse.",
			entrypoint: "flows/etl.py:daily_etl",
		}),
	},
};

export const EmptyDescription: Story = {
	name: "Empty State",
	args: {
		deployment: createFakeDeployment({
			description: null,
			entrypoint: "flows/etl.py:daily_etl",
		}),
	},
};

export const Deprecated: Story = {
	name: "Deprecated",
	args: {
		deployment: createFakeDeployment({
			entrypoint: null,
			description: null,
		}),
	},
};
