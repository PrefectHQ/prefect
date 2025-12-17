import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import type { EventsCountFilter, EventsFilter } from ".";
import { buildGetEventQuery, queryKeyFactory } from ".";

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
			const filter: EventsCountFilter = {
				filter: {
					occurred: {
						since: "2024-01-01T00:00:00.000Z",
						until: "2024-01-31T23:59:59.999Z",
					},
					order: "ASC",
				},
				time_unit: "hour",
				time_interval: 1,
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

		it("generates correct detail query key with eventId", () => {
			const eventId = "test-event-123";
			expect(queryKeyFactory.detail(eventId)).toEqual([
				"events",
				"detail",
				eventId,
				undefined,
			]);
		});

		it("generates correct detail query key with eventId and eventDate", () => {
			const eventId = "test-event-123";
			const eventDate = new Date("2024-06-15T14:30:00.000Z");
			expect(queryKeyFactory.detail(eventId, eventDate)).toEqual([
				"events",
				"detail",
				eventId,
				eventDate.toISOString(),
			]);
		});
	});

	describe("buildGetEventQuery", () => {
		it("creates query with correct queryKey including eventId and eventDate", () => {
			const eventId = "test-event-123";
			const eventDate = new Date("2024-06-15T14:30:00.000Z");

			const query = buildGetEventQuery(eventId, eventDate);

			expect(query.queryKey).toEqual([
				"events",
				"detail",
				eventId,
				eventDate.toISOString(),
			]);
		});

		it("returns query options with correct staleTime", () => {
			const eventId = "test-event-123";
			const eventDate = new Date("2024-06-15T14:30:00.000Z");

			const query = buildGetEventQuery(eventId, eventDate);

			expect(query.staleTime).toBe(60_000);
		});

		it("throws 'Event not found' error when no event is returned", async () => {
			const eventId = "nonexistent-event";
			const eventDate = new Date("2024-06-15T14:30:00.000Z");

			vi.mock("../service", () => ({
				getQueryService: () => ({
					POST: vi.fn().mockResolvedValue({ data: { events: [] } }),
				}),
			}));

			const query = buildGetEventQuery(eventId, eventDate);

			const queryFn = query.queryFn;
			if (!queryFn) {
				throw new Error("Expected queryFn to be defined");
			}

			const client = new QueryClient();
			const ctx = {
				client,
				queryKey: query.queryKey,
				signal: new AbortController().signal,
				meta: undefined,
			} as unknown as Parameters<typeof queryFn>[0];

			await expect(queryFn(ctx)).rejects.toThrow("Event not found");
		});
	});
});
