import { faker } from "@faker-js/faker";
import type { components } from "../../src/api/prefect";

export function generateRandomCronSchedule(): components["schemas"]["CronSchedule"] {
	return {
		cron: faker.system.cron(),
		timezone: faker.location.timeZone(),
		day_or: faker.datatype.boolean(),
	};
}

export function generateRandomIntervalSchedule(): components["schemas"]["IntervalSchedule"] {
	return {
		interval: faker.number.int({ min: 1, max: 100_000 }),
		anchor_date: faker.date.recent().toISOString(),
		timezone: faker.location.timeZone(),
	};
}

const frequencies = ["DAILY", "WEEKLY", "MONTHLY", "YEARLY"];
const weekdays = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"];

const getRandomWeekdays = () => {
	const shuffled = faker.helpers.shuffle(weekdays);
	const count = faker.number.int({ min: 1, max: 7 });
	return shuffled.slice(0, count).join(",");
};

export function generateRandomRRuleSchedule(): components["schemas"]["RRuleSchedule"] {
	const freq = faker.helpers.arrayElement(frequencies);
	const interval = faker.number.int({ min: 1, max: 10 });
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
			if (faker.datatype.boolean()) {
				const monthDay = faker.number.int({ min: 1, max: 28 });
				rruleComponents.push(`BYMONTHDAY=${monthDay}`);
			} else {
				const nth = faker.helpers.arrayElement(["1", "2", "3", "4", "-1"]);
				const day = faker.helpers.arrayElement(weekdays);
				rruleComponents.push(`BYDAY=${nth}${day}`);
			}
			addCountOrUntil(rruleComponents);
			break;
		}
		case "YEARLY": {
			const month = faker.number.int({ min: 1, max: 12 });
			const monthDay = faker.number.int({ min: 1, max: 28 });
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
		timezone: faker.location.timeZone(),
	};
}

function addCountOrUntil(rruleComponents: string[]) {
	if (faker.datatype.boolean()) {
		const count = faker.number.int({ min: 1, max: 100 });
		rruleComponents.push(`COUNT=${count}`);
	} else {
		const untilDate = faker.date.future();
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
	const selectedScheduleGenerator =
		faker.helpers.arrayElement(scheduleGenerators);
	return {
		id: faker.string.uuid(),
		created: faker.date.recent().toISOString(),
		updated: faker.date.recent().toISOString(),
		schedule: selectedScheduleGenerator(),
		active: faker.datatype.boolean(),
	};
}
