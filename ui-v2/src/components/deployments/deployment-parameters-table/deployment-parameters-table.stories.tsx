import type { Meta, StoryObj } from "@storybook/react";

import { createFakeDeployment } from "@/mocks";
import { DeploymentParametersTable } from "./deployment-parameters-table";

const meta = {
	title: "Components/Deployments/DeploymentParametersTable",
	component: DeploymentParametersTable,
	args: {
		deployment: createFakeDeployment({
			parameter_openapi_schema: {
				title: "Parameters",
				type: "object",
				properties: {
					name: {
						default: "world",
						position: 0,
						title: "name",
						type: "string",
					},
					goodbye: {
						default: false,
						position: 1,
						title: "goodbye",
						type: "boolean",
					},
				},
			},
			parameters: {
				goodbye: false,
				name: "world",
			},
		}),
	},
} satisfies Meta<typeof DeploymentParametersTable>;

export default meta;

export const story: StoryObj = { name: "DeploymentParametersTable" };
