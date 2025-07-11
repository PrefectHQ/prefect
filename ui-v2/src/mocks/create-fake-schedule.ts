import {
	rand,
	randBoolean,
	randFutureDate,
	randNumber,
	randRecentDate,
	randTimeZone,
	randUuid,
} from "@ngneat/falso";
import type { components } from "../../src/api/prefect";
import { randCron } from "./create-fake-cron";

export function generateRandomCronSchedule(): components["schemas"]["CronSchedule"] {
	return {
		cron: randCron(),
		timezone: randTimeZone(),
		day_or: randBoolean(),
	};
}

export function generateRandomIntervalSchedule(): components["schemas"]["IntervalSchedule"] {
	return {
		interval: randNumber({ min: 1, max: 100_000 }),
		anchor_date: randRecentDate().toISOString(),
		timezone: randTimeZone(),
	};
}

const frequencies = ["DAILY", "WEEKLY", "MONTHLY", "YEARLY"];
const weekdays = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"];

const getRandomWeekdays = () => {
	return rand(weekdays, {
		length: randNumber({ min: 1, max: 7 }),
		unique: true,
	}).join(",");
};

export function generateRandomRRuleSchedule(): components["schemas"]["RRuleSchedule"] {
	const freq = rand(frequencies);
	const interval = randNumber({ min: 1, max: 10 });
	const rruleComponents = [`FREQ=${freq}`, `INTERVAL=${interval}`];

	switch (freq) {
		case "DAILY":
			addCountOrUntil(rruleComponents);
			break;
		case "WEEKLY": {
			const byday = getRandomWeekdays();
			rruleComponents.push(`BYDAY=${byday}`);
			addCountOrUntil(rruleComponents);
			break;
		}
		case "MONTHLY": {
			if (randBoolean()) {
				const monthDay = randNumber({ min: 1, max: 28 });
				rruleComponents.push(`BYMONTHDAY=${monthDay}`);
			} else {
				const nth = rand(["1", "2", "3", "4", "-1"]);
				const day = rand(weekdays);
				rruleComponents.push(`BYDAY=${nth}${day}`);
			}
			addCountOrUntil(rruleComponents);
			break;
		}
		case "YEARLY": {
			const month = randNumber({ min: 1, max: 12 });
			const monthDay = randNumber({ min: 1, max: 28 });
			rruleComponents.push(`BYMONTH=${month}`, `BYMONTHDAY=${monthDay}`);
			addCountOrUntil(rruleComponents);
			break;
		}
		default:
			break;
	}

	const rruleString = rruleComponents.join(";");
	return {
		rrule: rruleString,
		timezone: randTimeZone(),
	};
}

function addCountOrUntil(rruleComponents: string[]) {
	if (randBoolean()) {
		const count = randNumber({ min: 1, max: 100 });
		rruleComponents.push(`COUNT=${count}`);
	} else {
		const untilDate = randFutureDate();
		const formattedUntil = formatDate(untilDate);
		rruleComponents.push(`UNTIL=${formattedUntil}`);
	}
}

function formatDate(date: Date) {
	const year = date.getUTCFullYear();
	const month = String(date.getUTCMonth() + 1).padStart(2, "0");
	const day = String(date.getUTCDate()).padStart(2, "0");
	return `${year}${month}${day}`;
}

const scheduleGenerators = [
	generateRandomCronSchedule,
	generateRandomIntervalSchedule,
	generateRandomRRuleSchedule,
];

export function createFakeSchedule(): components["schemas"]["DeploymentSchedule"] {
	const selectedScheduleGenerator = rand(scheduleGenerators);
	return {
		id: randUuid(),
		created: randRecentDate().toISOString(),
		updated: randRecentDate().toISOString(),
		schedule: selectedScheduleGenerator(),
		active: randBoolean(),
	};
}
