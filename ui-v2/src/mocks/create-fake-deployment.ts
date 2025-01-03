import { DeploymentWithFlow } from "@/api/deployments";
import { faker } from "@faker-js/faker";
import { createFakeSchedule } from "./create-fake-schedule";

export function createFakeDeployment(): DeploymentWithFlow {
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
		schedules: Array.from(
			{ length: faker.number.int({ min: 0, max: 3 }) },
			() => createFakeSchedule(),
		),
		flow: {
			id: faker.string.uuid(),
			created: faker.date.recent().toISOString(),
			updated: faker.date.recent().toISOString(),
			name: faker.company.catchPhrase().toLowerCase().replace(/\s+/g, "-"),
		},
	};
}
