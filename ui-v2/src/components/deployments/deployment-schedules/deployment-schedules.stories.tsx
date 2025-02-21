import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";

import { createFakeDeployment } from "@/mocks";
import { faker } from "@faker-js/faker";
import { DeploymentSchedules } from "./deployment-schedules";

const baseDeploymentSchedule = {
	id: faker.string.uuid(),
	created: faker.date.recent().toISOString(),
	updated: faker.date.recent().toISOString(),
	deployment_id: faker.string.uuid(),
	active: true,
	max_scheduled_runs: null,
};

const MOCK_DEPLOYMENT = createFakeDeployment({
	schedules: [
		{
			...baseDeploymentSchedule,
			schedule: {
				cron: "1 * * * *",
				timezone: "UTC",
				day_or: true,
			},
		},
		{
			...baseDeploymentSchedule,
			schedule: {
				cron: "1 * * * *",
				timezone: "UTC",
				day_or: true,
			},
		},
		{
			...baseDeploymentSchedule,
			schedule: {
				rrule: "FREQ=DAILY;COUNT=5",
				timezone: "UTC",
			},
		},
	],
});

const meta = {
	title: "Components/Deployments/DeploymentSchedules",
	component: DeploymentSchedules,
	decorators: [toastDecorator, routerDecorator, reactQueryDecorator],
	args: {
		deployment: MOCK_DEPLOYMENT,
	},
} satisfies Meta<typeof DeploymentSchedules>;

export default meta;

export const story: StoryObj = { name: "DeploymentSchedules" };
