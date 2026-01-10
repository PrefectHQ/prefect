import type { Meta, StoryObj } from "@storybook/react";
import { createFakeDeployment } from "@/mocks";
import { DeploymentMetadata } from "./deployment-metadata";

const meta = {
	title: "Components/Deployments/DeploymentMetadata",
	component: DeploymentMetadata,
} satisfies Meta<typeof DeploymentMetadata>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		deployment: createFakeDeployment({
			id: "deployment-123",
			flow_id: "flow-456",
			status: "READY",
			created: "2024-01-15T10:30:00Z",
			updated: "2024-01-15T12:00:00Z",
			entrypoint: "flows/my_flow.py:my_flow",
			path: "/app/flows",
			version: "v1.2.3",
			tags: ["production", "critical", "etl"],
		}),
	},
};

export const WithRepositoryUrl: Story = {
	args: {
		deployment: createFakeDeployment({
			id: "deployment-with-repo",
			flow_id: "flow-789",
			status: "READY",
			created: "2024-01-15T10:30:00Z",
			updated: "2024-01-15T12:00:00Z",
			entrypoint: "flows/my_flow.py:my_flow",
			path: "/app/flows",
			version: "v2.0.0",
			tags: ["production"],
			code_repository_url: "https://github.com/PrefectHQ/prefect",
		}),
	},
};

export const WithLongRepositoryUrl: Story = {
	args: {
		deployment: createFakeDeployment({
			id: "deployment-long-url",
			flow_id: "flow-101",
			status: "READY",
			code_repository_url:
				"https://github.com/my-organization/my-very-long-repository-name-that-might-wrap",
		}),
	},
};

export const WithoutRepositoryUrl: Story = {
	args: {
		deployment: createFakeDeployment({
			id: "deployment-no-repo",
			flow_id: "flow-202",
			status: "NOT_READY",
			code_repository_url: undefined,
		}),
	},
};

export const MinimalData: Story = {
	args: {
		deployment: createFakeDeployment({
			id: "minimal-deployment",
			flow_id: "minimal-flow",
			status: "READY",
			entrypoint: undefined,
			path: undefined,
			version: undefined,
			tags: [],
			code_repository_url: undefined,
		}),
	},
};
