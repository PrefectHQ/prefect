import type { DeploymentWithFlow } from "@/hooks/deployments";
import { faker } from "@faker-js/faker";
import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";
import { DeploymentsDataTable } from ".";

export default {
	title: "Components/Deployments/DataTable",
	component: DeploymentsDataTable,
} satisfies Meta<typeof DeploymentsDataTable>;

function createRandomDeployment(): DeploymentWithFlow {
	return {
		id: faker.string.uuid(),
		created: faker.date.recent().toISOString(),
		updated: faker.date.recent().toISOString(),
		name: faker.airline.airplane().name,
		flow_id: faker.string.uuid(),
		paused: faker.datatype.boolean(),
		status: faker.helpers.arrayElement(["READY", "NOT_READY"]),
		enforce_parameter_schema: faker.datatype.boolean(),
		tags: Array.from({ length: faker.number.int({ min: 0, max: 3 }) }, () =>
			faker.lorem.word(),
		),
		flow: {
			id: faker.string.uuid(),
			created: faker.date.recent().toISOString(),
			updated: faker.date.recent().toISOString(),
			name: faker.company.catchPhrase().toLowerCase().replace(/\s+/g, "-"),
		},
	};
}

export const Default: StoryObj = {
	name: "DataTable",
	args: {
		deployments: Array.from({ length: 10 }, createRandomDeployment),
		onQuickRun: fn(),
		onCustomRun: fn(),
		onEdit: fn(),
		onDelete: fn(),
		onDuplicate: fn(),
	},
};

export const Empty: StoryObj = {
	name: "Empty",
	args: {
		deployments: [],
	},
};
