import { describe, expect, it } from "vitest";
import { organizeFlowRunsWithGaps } from "./utils";

describe("organizeFlowRunsWithGaps", () => {
	const baseFlowRun = {
		id: "test-id",
		name: "test-run",
		state_type: "COMPLETED",
		total_run_time: 100,
		tags: [],
	};

	it("should return empty array if dates are missing", () => {
		const result = organizeFlowRunsWithGaps(
			[],
			undefined as unknown as Date,
			undefined as unknown as Date,
			10,
		);
		expect(result).toEqual([]);
	});

	it("should organize flow runs into correct number of buckets", () => {
		const startDate = new Date("2024-01-01");
		const endDate = new Date("2024-01-02");
		const numberOfBars = 5;

		const result = organizeFlowRunsWithGaps(
			[],
			startDate,
			endDate,
			numberOfBars,
		);
		expect(result).toHaveLength(numberOfBars);
		expect(result.every((bucket) => bucket === null)).toBe(true);
	});

	it("should place flow runs in correct buckets for past time range", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-01T10:00:00");
		const numberOfBars = 5;

		const flowRuns = [
			{
				...baseFlowRun,
				id: "1",
				start_time: "2024-01-01T02:00:00", // Should go in bucket 1
			},
			{
				...baseFlowRun,
				id: "2",
				start_time: "2024-01-01T08:00:00", // Should go in bucket 4
			},
		];

		const result = organizeFlowRunsWithGaps(
			// @ts-expect-error - Type error from test data not matching schema
			flowRuns,
			startDate,
			endDate,
			numberOfBars,
		);

		expect(result).toHaveLength(numberOfBars);
		expect(result[1]?.id).toBe("1");
		expect(result[4]?.id).toBe("2");
		expect(result[0]).toBeNull();
		expect(result[2]).toBeNull();
		expect(result[3]).toBeNull();
	});

	it("should handle future time ranges with expected_start_time", () => {
		const now = new Date();
		const startDate = now;
		const endDate = new Date(now.getTime() + 24 * 60 * 60 * 1000); // 24 hours later
		const numberOfBars = 5;

		const flowRuns = [
			{
				...baseFlowRun,
				id: "1",
				expected_start_time: new Date(
					now.getTime() + 4 * 60 * 60 * 1000,
				).toISOString(), // 4 hours in future
			},
			{
				...baseFlowRun,
				id: "2",
				expected_start_time: new Date(
					now.getTime() + 20 * 60 * 60 * 1000,
				).toISOString(), // 20 hours in future
			},
		];

		const result = organizeFlowRunsWithGaps(
			// @ts-expect-error - Type error from test data not matching schema
			flowRuns,
			startDate,
			endDate,
			numberOfBars,
		);

		expect(result).toHaveLength(numberOfBars);
		// buckets are roughly 4 hours apart so the first run should be in the first bucket
		// and the second run should be in the 5th bucket
		expect(result[0]?.id).toBe("1");
		expect(result[4]?.id).toBe("2");
	});

	it("should handle mixed past and future runs", () => {
		const now = new Date();
		const startDate = new Date(now.getTime() - 12 * 60 * 60 * 1000); // 12 hours ago
		const endDate = new Date(now.getTime() + 12 * 60 * 60 * 1000); // 12 hours in future
		const numberOfBars = 5;

		const flowRuns = [
			{
				...baseFlowRun,
				id: "1",
				start_time: new Date(now.getTime() - 6 * 60 * 60 * 1000).toISOString(), // 6 hours ago
			},
			{
				...baseFlowRun,
				id: "2",
				expected_start_time: new Date(
					now.getTime() + 6 * 60 * 60 * 1000,
				).toISOString(), // 6 hours in future
			},
		];

		const result = organizeFlowRunsWithGaps(
			// @ts-expect-error - Type error from test data not matching schema
			flowRuns,
			startDate,
			endDate,
			numberOfBars,
		);

		expect(result).toHaveLength(numberOfBars);
		// Verify that runs are placed in chronological order when the time span includes future dates
		expect(result.filter(Boolean)).toHaveLength(2);
	});

	it("should handle runs with missing start times", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-01T10:00:00");
		const numberOfBars = 5;

		const flowRuns = [
			{
				...baseFlowRun,
				id: "1",
				// Intentionally omitting both start_time and expected_start_time
			},
			{
				...baseFlowRun,
				id: "2",
				start_time: "2024-01-01T08:00:00",
			},
		];

		const result = organizeFlowRunsWithGaps(
			// @ts-expect-error - Type error from test data not matching schema
			flowRuns,
			startDate,
			endDate,
			numberOfBars,
		);

		expect(result).toHaveLength(numberOfBars);
		// Run with missing start time should be skipped
		expect(result.filter(Boolean)).toHaveLength(1);
		expect(result.find((r) => r?.id === "1")).toBeUndefined();
	});

	it("should throw an error if there are more runs than buckets", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-01T10:00:00");
		const numberOfBars = 2; // Intentionally small number of buckets

		const flowRuns = [
			{
				...baseFlowRun,
				id: "1",
				start_time: "2024-01-01T02:00:00",
			},
			{
				...baseFlowRun,
				id: "2",
				start_time: "2024-01-01T04:00:00",
			},
			{
				...baseFlowRun,
				id: "3",
				start_time: "2024-01-01T06:00:00",
			},
		];

		expect(() =>
			organizeFlowRunsWithGaps(
				// @ts-expect-error - Type error from test data not matching schema
				flowRuns,
				startDate,
				endDate,
				numberOfBars,
			),
		).toThrow(
			`Number of flow runs (${flowRuns.length}) is greater than the number of buckets (${numberOfBars})`,
		);
	});

	it("should sort runs chronologically for future time spans", () => {
		const now = new Date();
		const startDate = now;
		const endDate = new Date(now.getTime() + 24 * 60 * 60 * 1000);
		const numberOfBars = 5;

		const flowRuns = [
			{
				...baseFlowRun,
				id: "3",
				expected_start_time: new Date(
					now.getTime() + 20 * 60 * 60 * 1000,
				).toISOString(),
			},
			{
				...baseFlowRun,
				id: "1",
				expected_start_time: new Date(
					now.getTime() + 4 * 60 * 60 * 1000,
				).toISOString(),
			},
			{
				...baseFlowRun,
				id: "2",
				expected_start_time: new Date(
					now.getTime() + 12 * 60 * 60 * 1000,
				).toISOString(),
			},
		];

		const result = organizeFlowRunsWithGaps(
			// @ts-expect-error - Type error from test data not matching schema
			flowRuns,
			startDate,
			endDate,
			numberOfBars,
		);

		expect(result).toHaveLength(numberOfBars);
		// Verify chronological ordering
		const nonNullResults = result.filter(Boolean);
		expect(nonNullResults).toHaveLength(3);
		expect(nonNullResults[0]?.id).toBe("1");
		expect(nonNullResults[1]?.id).toBe("2");
		expect(nonNullResults[2]?.id).toBe("3");
	});

	it("should handle bucket allocation at boundaries", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-01T10:00:00");
		const numberOfBars = 3;

		const flowRuns = [
			{
				...baseFlowRun,
				id: "1",
				start_time: "2024-01-01T00:00:00", // At start boundary
			},
			{
				...baseFlowRun,
				id: "2",
				start_time: "2024-01-01T10:00:00", // At end boundary
			},
		];

		const result = organizeFlowRunsWithGaps(
			// @ts-expect-error - Type error from test data not matching schema
			flowRuns,
			startDate,
			endDate,
			numberOfBars,
		);

		expect(result).toHaveLength(numberOfBars);
		expect(result[0]?.id).toBe("1");
		expect(result[2]?.id).toBe("2");
	});

	it("should handle negative bucket indices", () => {
		const startDate = new Date("2024-01-01T00:00:00");
		const endDate = new Date("2024-01-01T10:00:00");
		const numberOfBars = 3;

		const flowRuns = [
			{
				...baseFlowRun,
				id: "1",
				start_time: "2023-12-31T23:59:59", // Just before start date
			},
			{
				...baseFlowRun,
				id: "2",
				start_time: "2024-01-01T05:00:00", // Middle of range
			},
		];

		const result = organizeFlowRunsWithGaps(
			// @ts-expect-error - Type error from test data not matching schema
			flowRuns,
			startDate,
			endDate,
			numberOfBars,
		);

		expect(result).toHaveLength(numberOfBars);
		// Run with negative bucket index should be skipped
		expect(result.find((r) => r?.id === "1")).toBeUndefined();
		expect(result[1]?.id).toBe("2");
	});

	it("should handle sequential bucket allocation with gaps", () => {
		const now = new Date();
		const startDate = now;
		const endDate = new Date(now.getTime() + 10 * 60 * 60 * 1000); // 10 hours ahead
		const numberOfBars = 5;

		const flowRuns = [
			{
				...baseFlowRun,
				id: "1",
				expected_start_time: new Date(
					now.getTime() + 2 * 60 * 60 * 1000,
				).toISOString(),
			},
			{
				...baseFlowRun,
				id: "2",
				expected_start_time: new Date(
					now.getTime() + 3 * 60 * 60 * 1000,
				).toISOString(),
			},
			{
				...baseFlowRun,
				id: "3",
				expected_start_time: new Date(
					now.getTime() + 3 * 60 * 60 * 1000,
				).toISOString(),
			},
		];

		const result = organizeFlowRunsWithGaps(
			// @ts-expect-error - Type error from test data not matching schema
			flowRuns,
			startDate,
			endDate,
			numberOfBars,
		);

		expect(result).toHaveLength(numberOfBars);
		// Verify sequential allocation with proper gaps
		expect(result[0]).toBe(null);
		expect(result[1]?.id).toBe("1");
		expect(result[2]?.id).toBe("2");
		expect(result[3]?.id).toBe("3");
		expect(result[4]).toBeNull();
	});
});
