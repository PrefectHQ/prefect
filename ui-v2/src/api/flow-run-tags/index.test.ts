import { describe, expect, test, vi } from "vitest";
import { buildListFlowRunTagsQuery } from "./index";

// Mock the flow-runs API
vi.mock("@/api/flow-runs", () => ({
	buildFilterFlowRunsQuery: vi.fn(() => ({
		queryFn: vi.fn(),
	})),
}));

describe("buildListFlowRunTagsQuery", () => {
	test("returns correct query key", () => {
		const query = buildListFlowRunTagsQuery();
		expect(query.queryKey).toEqual(["flowRunTags", "list"]);
	});

	test("has correct stale and gc times", () => {
		const query = buildListFlowRunTagsQuery();
		expect(query.staleTime).toBe(5 * 60 * 1000); // 5 minutes
		expect(query.gcTime).toBe(10 * 60 * 1000); // 10 minutes
	});

	test("queryFn extracts and deduplicates tags from flow runs", async () => {
		const mockFlowRuns = [
			{ tags: ["production", "critical"] },
			{ tags: ["staging", "production"] }, // duplicate 'production'
			{ tags: ["development"] },
			{ tags: null }, // null tags
			{ tags: undefined }, // undefined tags
			{ tags: [] }, // empty tags
			{ tags: ["production", "PRODUCTION"] }, // case sensitivity test
			{ tags: ["  spaced  ", "normal"] }, // whitespace test
			{ tags: [""] }, // empty string tag
		];

		const mockFlowRunsQuery = {
			queryFn: vi.fn().mockResolvedValue(mockFlowRuns),
		};

		vi.mocked(
			require("@/api/flow-runs").buildFilterFlowRunsQuery,
		).mockReturnValue(mockFlowRunsQuery);

		const query = buildListFlowRunTagsQuery();
		const result = await query.queryFn();

		expect(result).toEqual([
			"critical",
			"development",
			"normal",
			"PRODUCTION",
			"production",
			"spaced",
			"staging",
		]);
	});

	test("handles flow runs with non-array tags", async () => {
		const mockFlowRuns = [
			{ tags: "not-an-array" },
			{ tags: 123 },
			{ tags: { not: "array" } },
			{ tags: ["valid-tag"] },
		];

		const mockFlowRunsQuery = {
			queryFn: vi.fn().mockResolvedValue(mockFlowRuns),
		};

		vi.mocked(
			require("@/api/flow-runs").buildFilterFlowRunsQuery,
		).mockReturnValue(mockFlowRunsQuery);

		const query = buildListFlowRunTagsQuery();
		const result = await query.queryFn();

		expect(result).toEqual(["valid-tag"]);
	});

	test("handles flow runs with non-string tag values", async () => {
		const mockFlowRuns = [
			{ tags: ["valid-string", 123, null, undefined, {}, []] },
			{ tags: ["another-valid"] },
		];

		const mockFlowRunsQuery = {
			queryFn: vi.fn().mockResolvedValue(mockFlowRuns),
		};

		vi.mocked(
			require("@/api/flow-runs").buildFilterFlowRunsQuery,
		).mockReturnValue(mockFlowRunsQuery);

		const query = buildListFlowRunTagsQuery();
		const result = await query.queryFn();

		expect(result).toEqual(["another-valid", "valid-string"]);
	});

	test("returns empty array when no flow runs have tags", async () => {
		const mockFlowRuns = [
			{ tags: null },
			{ tags: undefined },
			{ tags: [] },
			{}, // no tags property
		];

		const mockFlowRunsQuery = {
			queryFn: vi.fn().mockResolvedValue(mockFlowRuns),
		};

		vi.mocked(
			require("@/api/flow-runs").buildFilterFlowRunsQuery,
		).mockReturnValue(mockFlowRunsQuery);

		const query = buildListFlowRunTagsQuery();
		const result = await query.queryFn();

		expect(result).toEqual([]);
	});

	test("returns empty array when no flow runs exist", async () => {
		const mockFlowRunsQuery = {
			queryFn: vi.fn().mockResolvedValue([]),
		};

		vi.mocked(
			require("@/api/flow-runs").buildFilterFlowRunsQuery,
		).mockReturnValue(mockFlowRunsQuery);

		const query = buildListFlowRunTagsQuery();
		const result = await query.queryFn();

		expect(result).toEqual([]);
	});

	test("sorts tags alphabetically (case-insensitive)", async () => {
		const mockFlowRuns = [{ tags: ["zebra", "Apple", "banana", "Cherry"] }];

		const mockFlowRunsQuery = {
			queryFn: vi.fn().mockResolvedValue(mockFlowRuns),
		};

		vi.mocked(
			require("@/api/flow-runs").buildFilterFlowRunsQuery,
		).mockReturnValue(mockFlowRunsQuery);

		const query = buildListFlowRunTagsQuery();
		const result = await query.queryFn();

		expect(result).toEqual(["Apple", "banana", "Cherry", "zebra"]);
	});

	test("calls buildFilterFlowRunsQuery with correct parameters", async () => {
		const mockFlowRunsQuery = {
			queryFn: vi.fn().mockResolvedValue([]),
		};

		const buildFilterFlowRunsQueryMock = vi.mocked(
			require("@/api/flow-runs").buildFilterFlowRunsQuery,
		);
		buildFilterFlowRunsQueryMock.mockReturnValue(mockFlowRunsQuery);

		const query = buildListFlowRunTagsQuery();
		await query.queryFn();

		expect(buildFilterFlowRunsQueryMock).toHaveBeenCalledWith({
			limit: 1000,
			sort: "CREATED_DESC",
			offset: 0,
		});
	});
});
