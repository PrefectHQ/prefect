import { describe, expect, it, vi } from "vitest";
import { buildListFlowRunTagsQuery } from "./index";

// Mock the query service
const mockPost = vi.fn();
vi.mock("@/api/service", () => ({
	getQueryService: () => ({
		POST: mockPost,
	}),
}));

describe("buildListFlowRunTagsQuery", () => {
	beforeEach(() => {
		mockPost.mockClear();
	});

	it("creates query with correct default parameters", () => {
		const query = buildListFlowRunTagsQuery();

		expect(query.queryKey).toEqual(["flowRuns", "tags", 1000]);
		expect(query.staleTime).toBe(5 * 60 * 1000); // 5 minutes
	});

	it("creates query with custom limit parameter", () => {
		const query = buildListFlowRunTagsQuery(500);

		expect(query.queryKey).toEqual(["flowRuns", "tags", 500]);
	});

	it("extracts unique tags from flow runs data", async () => {
		const mockFlowRuns = [
			{ id: "1", tags: ["production", "urgent"] },
			{ id: "2", tags: ["staging", "production"] },
			{ id: "3", tags: ["development"] },
			{ id: "4", tags: ["production", "test"] },
		];

		mockPost.mockResolvedValueOnce({ data: mockFlowRuns });

		const query = buildListFlowRunTagsQuery();
		const result = await query.queryFn();

		expect(mockPost).toHaveBeenCalledWith("/flow_runs/filter", {
			body: {
				sort: "START_TIME_DESC",
				offset: 0,
				limit: 1000,
			},
		});

		expect(result).toEqual([
			"development",
			"production",
			"staging",
			"test",
			"urgent",
		]);
	});

	it("handles flow runs without tags", async () => {
		const mockFlowRuns = [
			{ id: "1", tags: ["production"] },
			{ id: "2", tags: null },
			{ id: "3", tags: undefined },
			{ id: "4", tags: ["staging"] },
		];

		mockPost.mockResolvedValueOnce({ data: mockFlowRuns });

		const query = buildListFlowRunTagsQuery();
		const result = await query.queryFn();

		expect(result).toEqual(["production", "staging"]);
	});

	it("returns empty array when no data is returned", async () => {
		mockPost.mockResolvedValueOnce({ data: null });

		const query = buildListFlowRunTagsQuery();
		const result = await query.queryFn();

		expect(result).toEqual([]);
	});

	it("returns empty array when flow runs array is empty", async () => {
		mockPost.mockResolvedValueOnce({ data: [] });

		const query = buildListFlowRunTagsQuery();
		const result = await query.queryFn();

		expect(result).toEqual([]);
	});

	it("deduplicates and sorts tags correctly", async () => {
		const mockFlowRuns = [
			{ id: "1", tags: ["zebra", "alpha", "beta"] },
			{ id: "2", tags: ["alpha", "gamma", "beta"] },
			{ id: "3", tags: ["zebra", "alpha"] },
		];

		mockPost.mockResolvedValueOnce({ data: mockFlowRuns });

		const query = buildListFlowRunTagsQuery();
		const result = await query.queryFn();

		// Should be alphabetically sorted and deduplicated
		expect(result).toEqual(["alpha", "beta", "gamma", "zebra"]);
	});
});
