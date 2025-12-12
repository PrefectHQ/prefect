import { describe, expect, it } from "vitest";
import type { EventsCountFilter, EventsFilter } from ".";
import { queryKeyFactory } from ".";

describe("events api", () => {
	describe("queryKeyFactory", () => {
		it("generates correct base query keys", () => {
			expect(queryKeyFactory.all()).toEqual(["events"]);
			expect(queryKeyFactory.lists()).toEqual(["events", "list"]);
			expect(queryKeyFactory["lists-filter"]()).toEqual([
				"events",
				"list",
				"filter",
			]);
			expect(queryKeyFactory.counts()).toEqual(["events", "counts"]);
			expect(queryKeyFactory.history()).toEqual(["events", "history"]);
		});

		it("generates correct list-filter query key with filter", () => {
			const filter: EventsFilter = {
				filter: {
					any_resource: {
						id: ["prefect.flow-run.123"],
					},
					event: {
						exclude_prefix: ["prefect.log.write"],
					},
					order: "DESC",
				},
				limit: 100,
			};

			expect(queryKeyFactory["list-filter"](filter)).toEqual([
				"events",
				"list",
				"filter",
				filter,
			]);
		});

		it("generates correct count query key with countable and filter", () => {
			const countable = "day";
			const filter: EventsCountFilter = {
				filter: {
					occurred: {
						since: "2024-01-01T00:00:00.000Z",
						until: "2024-01-31T23:59:59.999Z",
					},
					order: "DESC",
				},
				time_unit: "day",
				time_interval: 1,
			};

			expect(queryKeyFactory.count(countable, filter)).toEqual([
				"events",
				"counts",
				countable,
				filter,
			]);
		});

		it("generates correct historyFilter query key with filter", () => {
			const filter: EventsFilter = {
				filter: {
					any_resource: {
						id: ["prefect.flow-run.456"],
					},
					order: "ASC",
				},
				limit: 50,
			};

			expect(queryKeyFactory.historyFilter(filter)).toEqual([
				"events",
				"history",
				filter,
			]);
		});

		it("maintains hierarchical key structure for cache invalidation", () => {
			const filter: EventsFilter = { limit: 10 };

			const listFilterKey = queryKeyFactory["list-filter"](filter);
			const listsFilterKey = queryKeyFactory["lists-filter"]();
			const listsKey = queryKeyFactory.lists();
			const allKey = queryKeyFactory.all();

			expect(listFilterKey.slice(0, 3)).toEqual(listsFilterKey);
			expect(listsFilterKey.slice(0, 2)).toEqual(listsKey);
			expect(listsKey.slice(0, 1)).toEqual(allKey);
		});
	});
});
