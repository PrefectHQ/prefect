import { faker } from "@faker-js/faker";
import type { Meta, StoryObj } from "@storybook/react";
import {
	createRandomCronSchedule,
	createRandomIntervalSchedule,
	generateRandomRRuleSchedule,
} from "@tests/utils/mock-factories";
import { ScheduleBadge } from ".";

export default {
	title: "UI/ScheduleBadge",
	component: ScheduleBadge,
} satisfies Meta<typeof ScheduleBadge>;

type Story = StoryObj<typeof ScheduleBadge>;

export const CronSchedule: Story = {
	args: {
		schedule: {
			id: faker.string.uuid(),
			created: faker.date.recent().toISOString(),
			updated: faker.date.recent().toISOString(),
			deployment_id: faker.string.uuid(),
			active: faker.datatype.boolean(),
			max_scheduled_runs: faker.number.int({ min: 1, max: 100 }),
			schedule: createRandomCronSchedule(),
		},
	},
};

export const IntervalSchedule: Story = {
	args: {
		schedule: {
			id: faker.string.uuid(),
			created: faker.date.recent().toISOString(),
			updated: faker.date.recent().toISOString(),
			deployment_id: faker.string.uuid(),
			active: faker.datatype.boolean(),
			max_scheduled_runs: faker.number.int({ min: 1, max: 100 }),
			schedule: createRandomIntervalSchedule(),
		},
	},
};

export const RRuleSchedule: Story = {
	args: {
		schedule: {
			id: faker.string.uuid(),
			created: faker.date.recent().toISOString(),
			updated: faker.date.recent().toISOString(),
			deployment_id: faker.string.uuid(),
			active: faker.datatype.boolean(),
			max_scheduled_runs: faker.number.int({ min: 1, max: 100 }),
			schedule: generateRandomRRuleSchedule(),
		},
	},
};
