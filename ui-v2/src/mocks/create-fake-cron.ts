/**
 * This is a copy of the `faker.system.cron` function from the `faker` package modified to use falso utilities.
 * This was done to avoid adding the `faker` package to the project dependencies and because falso does not have a cron generator.
 * https://github.com/faker-js/faker/blob/next/src/modules/system/index.ts#L316
 */

import { rand, randBoolean, randNumber } from "@ngneat/falso";

const CRON_DAY_OF_WEEK = [
	"SUN",
	"MON",
	"TUE",
	"WED",
	"THU",
	"FRI",
	"SAT",
] as const;

/**
 * Returns a random cron expression.
 *
 * @param options The optional options to use.
 * @param options.includeYear Whether to include a year in the generated expression. Defaults to `false`.
 * @param options.includeNonStandard Whether to include a `@yearly`, `@monthly`, `@daily`, etc text labels in the generated expression. Defaults to `false`.
 *
 * @example
 * faker.system.cron() // '45 23 * * 6'
 * faker.system.cron({ includeYear: true }) // '45 23 * * 6 2067'
 * faker.system.cron({ includeYear: false }) // '45 23 * * 6'
 * faker.system.cron({ includeNonStandard: false }) // '45 23 * * 6'
 * faker.system.cron({ includeNonStandard: true }) // '@yearly'
 *
 * @since 7.5.0
 */
export function randCron(
	options: {
		/**
		 * Whether to include a year in the generated expression.
		 *
		 * @default false
		 */
		includeYear?: boolean;
		/**
		 * Whether to include a `@yearly`, `@monthly`, `@daily`, etc text labels in the generated expression.
		 *
		 * @default false
		 */
		includeNonStandard?: boolean;
	} = {},
): string {
	const { includeYear = false, includeNonStandard = false } = options;

	// create the arrays to hold the available values for each component of the expression
	const minutes = [randNumber({ min: 0, max: 59 }), "*"];
	const hours = [randNumber({ min: 0, max: 23 }), "*"];
	const days = [randNumber({ min: 1, max: 31 }), "*", "?"];
	const months = [randNumber({ min: 1, max: 12 }), "*"];
	const daysOfWeek = [
		randNumber({ min: 0, max: 6 }),
		rand(CRON_DAY_OF_WEEK),
		"*",
		"?",
	];
	const years = [randNumber({ min: 1970, max: 2099 }), "*"];

	const minute = rand(minutes);
	const hour = rand(hours);
	const day = rand(days);
	const month = rand(months);
	const dayOfWeek = rand(daysOfWeek);
	const year = rand(years);

	// create and return the cron expression string
	let standardExpression = `${minute} ${hour} ${day} ${month} ${dayOfWeek}`;
	if (includeYear) {
		standardExpression += ` ${year}`;
	}

	const nonStandardExpressions = [
		"@annually",
		"@daily",
		"@hourly",
		"@monthly",
		"@reboot",
		"@weekly",
		"@yearly",
	];

	return !includeNonStandard || randBoolean()
		? standardExpression
		: rand(nonStandardExpressions);
}
