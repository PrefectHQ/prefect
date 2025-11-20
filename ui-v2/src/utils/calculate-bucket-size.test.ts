import { expect, test } from "vitest";
import { calculateBucketSize } from "./calculate-bucket-size";

test("should return 'hour' for ranges less than 3 days", () => {
	const startDate = new Date("2024-01-01T00:00:00Z");
	const endDate = new Date("2024-01-02T12:00:00Z");

	const RESULT = calculateBucketSize(startDate, endDate);
	const EXPECTED = "hour";

	expect(RESULT).toEqual(EXPECTED);
});

test("should return 'hour' for 2.9 days (boundary case)", () => {
	const startDate = new Date("2024-01-01T00:00:00Z");
	const endDate = new Date(startDate.getTime() + 2.9 * 24 * 60 * 60 * 1000);

	const RESULT = calculateBucketSize(startDate, endDate);
	const EXPECTED = "hour";

	expect(RESULT).toEqual(EXPECTED);
});

test("should return 'day' for exactly 3 days (boundary case)", () => {
	const startDate = new Date("2024-01-01T00:00:00Z");
	const endDate = new Date("2024-01-04T00:00:00Z");

	const RESULT = calculateBucketSize(startDate, endDate);
	const EXPECTED = "day";

	expect(RESULT).toEqual(EXPECTED);
});

test("should return 'day' for ranges between 3 and 30 days", () => {
	const startDate = new Date("2024-01-01T00:00:00Z");
	const endDate = new Date("2024-01-15T00:00:00Z");

	const RESULT = calculateBucketSize(startDate, endDate);
	const EXPECTED = "day";

	expect(RESULT).toEqual(EXPECTED);
});

test("should return 'day' for 29.9 days (boundary case)", () => {
	const startDate = new Date("2024-01-01T00:00:00Z");
	const endDate = new Date(startDate.getTime() + 29.9 * 24 * 60 * 60 * 1000);

	const RESULT = calculateBucketSize(startDate, endDate);
	const EXPECTED = "day";

	expect(RESULT).toEqual(EXPECTED);
});

test("should return 'week' for exactly 30 days (boundary case)", () => {
	const startDate = new Date("2024-01-01T00:00:00Z");
	const endDate = new Date("2024-01-31T00:00:00Z");

	const RESULT = calculateBucketSize(startDate, endDate);
	const EXPECTED = "week";

	expect(RESULT).toEqual(EXPECTED);
});

test("should return 'week' for ranges 30 days or more", () => {
	const startDate = new Date("2024-01-01T00:00:00Z");
	const endDate = new Date("2024-03-01T00:00:00Z");

	const RESULT = calculateBucketSize(startDate, endDate);
	const EXPECTED = "week";

	expect(RESULT).toEqual(EXPECTED);
});

test("should return 'week' for 365 days (large range edge case)", () => {
	const startDate = new Date("2024-01-01T00:00:00Z");
	const endDate = new Date("2025-01-01T00:00:00Z");

	const RESULT = calculateBucketSize(startDate, endDate);
	const EXPECTED = "week";

	expect(RESULT).toEqual(EXPECTED);
});

test("should return 'hour' for same start and end date (0 days edge case)", () => {
	const startDate = new Date("2024-01-01T00:00:00Z");
	const endDate = new Date("2024-01-01T00:00:00Z");

	const RESULT = calculateBucketSize(startDate, endDate);
	const EXPECTED = "hour";

	expect(RESULT).toEqual(EXPECTED);
});

test("should handle negative range gracefully (end date before start date)", () => {
	const startDate = new Date("2024-01-10T00:00:00Z");
	const endDate = new Date("2024-01-01T00:00:00Z");

	const RESULT = calculateBucketSize(startDate, endDate);
	const EXPECTED = "hour";

	expect(RESULT).toEqual(EXPECTED);
});
