import { expect, test } from "vitest";
import { secondsToApproximateString, secondsToString } from "./seconds";

// Regression tests for https://github.com/PrefectHQ/prefect/issues/17039
// Fractional seconds were rounded up without carrying into the next unit,
// producing impossible durations like "4m 60s".

test("carries a rounded-up second into minutes", () => {
	const RESULT = secondsToApproximateString(299.5);
	const EXPECTED = "5m";

	expect(RESULT).toEqual(EXPECTED);
});

test("carries through minutes into hours", () => {
	const RESULT = secondsToApproximateString(3599.5);
	// Note: an exact hour renders as "1h 0m" both before and after this fix;
	// that quirk lives in the switch in secondsToApproximateString and is out of scope.
	const EXPECTED = "1h 0m";

	expect(RESULT).toEqual(EXPECTED);
});

test("carries through hours into days", () => {
	const RESULT = secondsToApproximateString(86399.5);
	const EXPECTED = "1d";

	expect(RESULT).toEqual(EXPECTED);
});

test("never renders 60 seconds", () => {
	const RESULT = secondsToApproximateString(59.5);
	const EXPECTED = "1m";

	expect(RESULT).toEqual(EXPECTED);
});

test("carries in the long-form string as well", () => {
	const RESULT = secondsToString(299.5);
	const EXPECTED = "5 minutes";

	expect(RESULT).toEqual(EXPECTED);
});

// Behavior that must not regress: sub-second durations still round up to 1s
// rather than displaying as "0s".

test("sub-second durations still display as 1s", () => {
	const RESULT = secondsToApproximateString(0.4);
	const EXPECTED = "1s";

	expect(RESULT).toEqual(EXPECTED);
});

test("whole values are unchanged", () => {
	expect(secondsToApproximateString(25)).toEqual("25s");
	expect(secondsToApproximateString(3661)).toEqual("1h 1m");
	expect(secondsToApproximateString(90061)).toEqual("1d 1h");
	expect(secondsToString(3661)).toEqual("1 hour 1 minute 1 second");
});
