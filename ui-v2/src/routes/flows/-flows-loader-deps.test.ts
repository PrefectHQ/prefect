import { describe, expect, it } from "vitest";
import { buildFlowsLoaderDeps, searchParams } from "./index";

describe("flows loader deps", () => {
	it("keeps the same deps when a search starts from page 2 (first edit keeps focus)", () => {
		const before = searchParams.parse({ page: 2 });
		// First keystroke in the name search: the filter hook resets page to 1.
		const afterFirstEdit = searchParams.parse({
			page: 1,
			name: "my-flow",
		});
		expect(buildFlowsLoaderDeps(afterFirstEdit)).toEqual(
			buildFlowsLoaderDeps(before),
		);
	});

	it("keeps the same deps when paging (page is UI state, not loader data)", () => {
		expect(buildFlowsLoaderDeps(searchParams.parse({ page: 2 }))).toEqual(
			buildFlowsLoaderDeps(searchParams.parse({ page: 1 })),
		);
	});

	it("keeps the same deps across name and tag edits", () => {
		expect(buildFlowsLoaderDeps(searchParams.parse({ name: "a" }))).toEqual(
			buildFlowsLoaderDeps(searchParams.parse({ name: "ab" })),
		);
		expect(
			buildFlowsLoaderDeps(searchParams.parse({ tags: ["a"] })),
		).toEqual(
			buildFlowsLoaderDeps(searchParams.parse({ tags: ["a", "b"] })),
		);
	});

	it("changes deps when sort changes (sort affects the data fetched)", () => {
		expect(
			buildFlowsLoaderDeps(searchParams.parse({ sort: "NAME_ASC" })),
		).not.toEqual(
			buildFlowsLoaderDeps(searchParams.parse({ sort: "CREATED_DESC" })),
		);
	});
});
