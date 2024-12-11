import type { DeploymentWithFlow } from "@/hooks/deployments";
import { faker } from "@faker-js/faker";
import type { Meta, StoryObj } from "@storybook/react";
import { DeploymentsDataTable } from ".";

export default {
	title: "Components/Deployments/DataTable",
	component: DeploymentsDataTable,
} satisfies Meta<typeof DeploymentsDataTable>;

function createRandomDeployment(): DeploymentWithFlow {
	return {
		id: faker.string.uuid(),
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
			name: faker.company.catchPhrase().toLowerCase().replace(/\s+/g, "-"),
		},
	};
}

export const Default: StoryObj = {
	name: "DataTable",
	args: { deployments: Array.from({ length: 10 }, createRandomDeployment) },
};
