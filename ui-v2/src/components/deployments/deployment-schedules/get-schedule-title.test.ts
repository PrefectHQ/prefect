import type { DeploymentSchedule } from "@/api/deployments";
import { faker } from "@faker-js/faker";
import { describe, expect, it } from "vitest";
import { getScheduleTitle } from "./get-schedule-title";

describe("getScheduleTitle()", () => {
	const baseDeploymentSchedule = {
		id: faker.string.uuid(),
		created: faker.date.recent().toISOString(),
		updated: faker.date.recent().toISOString(),
		deployment_id: faker.string.uuid(),
		active: true,
		max_scheduled_runs: null,
	};

	it("returns an interval formatted title", () => {
		const mockDeploymentSchedule: DeploymentSchedule = {
			...baseDeploymentSchedule,
			schedule: {
				interval: 3600,
				anchor_date: faker.date.recent().toISOString(),
				timezone: "UTC",
			},
		};

		// TEST
		const RESULT = getScheduleTitle(mockDeploymentSchedule);

		// ASSERT
		const EXPECTED = "Every 1 hour";
		expect(RESULT).toEqual(EXPECTED);
	});

	it("returns a cron formatted title", () => {
		const mockDeploymentSchedule: DeploymentSchedule = {
			...baseDeploymentSchedule,
			schedule: {
				cron: "1 * * * *",
				timezone: "UTC",
				day_or: true,
			},
		};

		// TEST
		const RESULT = getScheduleTitle(mockDeploymentSchedule);

		// ASSERT
		const EXPECTED = "At 1 minutes past the hour";
		expect(RESULT).toEqual(EXPECTED);
	});

	it("returns a rrule formatted title", () => {
		const mockDeploymentSchedule: DeploymentSchedule = {
			...baseDeploymentSchedule,
			schedule: {
				rrule: "FREQ=DAILY;COUNT=5",
				timezone: "UTC",
			},
		};

		// TEST
		const RESULT = getScheduleTitle(mockDeploymentSchedule);

		// ASSERT
		const EXPECTED = "every day for 5 times";
		expect(RESULT).toEqual(EXPECTED);
	});
});
