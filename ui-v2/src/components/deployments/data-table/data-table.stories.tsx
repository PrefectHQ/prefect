import type { Meta, StoryObj } from "@storybook/react";
import { DeploymentsDataTable } from ".";

export default {
	title: "Components/Deployments/DataTable",
	component: DeploymentsDataTable,
	parameters: {
		layout: "centered",
	},
} satisfies Meta<typeof DeploymentsDataTable>;

export const Default: StoryObj = {
	name: "DataTable",
	args: { deployments: [] },
};
