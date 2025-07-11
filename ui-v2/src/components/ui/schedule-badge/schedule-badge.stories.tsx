import {
	randBoolean,
	randNumber,
	randRecentDate,
	randUuid,
} from "@ngneat/falso";
import type { Meta, StoryObj } from "@storybook/react";
import {
	generateRandomCronSchedule,
	generateRandomIntervalSchedule,
	generateRandomRRuleSchedule,
} from "@/mocks/create-fake-schedule";
import { ScheduleBadge } from ".";

export default {
	title: "UI/ScheduleBadge",
	component: ScheduleBadge,
	parameters: {
		layout: "centered",
	},
} satisfies Meta<typeof ScheduleBadge>;

type Story = StoryObj<typeof ScheduleBadge>;

export const CronSchedule: Story = {
	args: {
		schedule: {
			id: randUuid(),
			created: randRecentDate().toISOString(),
			updated: randRecentDate().toISOString(),
			deployment_id: randUuid(),
			active: randBoolean(),
			max_scheduled_runs: randNumber({ min: 1, max: 100 }),
			schedule: generateRandomCronSchedule(),
		},
	},
};

export const IntervalSchedule: Story = {
	args: {
		schedule: {
			id: randUuid(),
			created: randRecentDate().toISOString(),
			updated: randRecentDate().toISOString(),
			deployment_id: randUuid(),
			active: randBoolean(),
			max_scheduled_runs: randNumber({ min: 1, max: 100 }),
			schedule: generateRandomIntervalSchedule(),
		},
	},
};

export const RRuleSchedule: Story = {
	args: {
		schedule: {
			id: randUuid(),
			created: randRecentDate().toISOString(),
			updated: randRecentDate().toISOString(),
			deployment_id: randUuid(),
			active: randBoolean(),
			max_scheduled_runs: randNumber({ min: 1, max: 100 }),
			schedule: generateRandomRRuleSchedule(),
		},
	},
};
