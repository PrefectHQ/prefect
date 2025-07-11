import {
	rand,
	randBoolean,
	randNumber,
	randPastDate,
	randProductName,
	randRecentDate,
	randUuid,
	randWord,
} from "@ngneat/falso";
import type { components } from "@/api/prefect";
import { createFakeSchedule } from "./create-fake-schedule";

export function createFakeDeployment(
	overrides?: Partial<components["schemas"]["DeploymentResponse"]>,
): components["schemas"]["DeploymentResponse"] {
	return {
		id: randUuid(),
		created: randPastDate().toISOString(),
		updated: randPastDate().toISOString(),
		name: randProductName(),
		flow_id: randUuid(),
		paused: randBoolean(),
		status: rand(["READY", "NOT_READY"]),
		enforce_parameter_schema: randBoolean(),
		tags: randWord({ length: randNumber({ min: 0, max: 3 }) }),
		schedules: Array.from({ length: randNumber({ min: 0, max: 3 }) }, () =>
			createFakeSchedule(),
		),
		...overrides,
	};
}

export function createFakeDeploymentWithFlow(
	overrides?: Partial<components["schemas"]["DeploymentResponse"]>,
) {
	return {
		...createFakeDeployment(overrides),
		flow: {
			id: randUuid(),
			created: randRecentDate().toISOString(),
			updated: randRecentDate().toISOString(),
			name: randProductName().toLowerCase().replace(/\s+/g, "-"),
		},
	};
}
