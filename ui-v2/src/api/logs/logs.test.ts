import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import type { components } from "@/api/prefect";
import { buildFilterLogsQuery, queryKeyFactory } from ".";

type Log = components["schemas"]["Log"];

describe("logs api", () => {
	const mockFetchLogsAPI = (logs: Array<Log>) => {
		server.use(
			http.post(buildApiUrl("/logs/filter"), () => {
				return HttpResponse.json(logs);
			}),
		);
	};

	describe("queryKeyFactory", () => {
		it("generates correct query keys", () => {
			expect(queryKeyFactory.all()).toEqual(["logs"]);
			expect(queryKeyFactory.lists()).toEqual(["logs", "list"]);

			const filter = {
				logs: { operator: "and_", level: { ge_: 0 } },
				sort: "TIMESTAMP_ASC",
				offset: 0,
				limit: 100,
			} as const;

			expect(queryKeyFactory.list(filter)).toEqual(["logs", "list", filter]);
		});
	});

	describe("buildFilterLogsQuery", () => {
		it("fetches logs with default parameters", async () => {
			const mockLogs = [
				{ id: "1", level: 20, message: "Test log 1" },
				{ id: "2", level: 30, message: "Test log 2" },
			] as Log[];

			mockFetchLogsAPI(mockLogs);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() =>
					useSuspenseQuery(
						buildFilterLogsQuery({
							offset: 0,
							sort: "TIMESTAMP_ASC",
							limit: 100,
						}),
					),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toEqual(mockLogs);
			});
		});

		it("fetches logs with custom filter parameters", async () => {
			const mockLogs = [{ id: "1", level: 40, message: "Error log" }] as Log[];

			mockFetchLogsAPI(mockLogs);

			const filter = {
				logs: {
					operator: "and_",
					level: { ge_: 40 },
				},
				sort: "TIMESTAMP_DESC",
				offset: 0,
				limit: 50,
			} as const;

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildFilterLogsQuery(filter)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual(mockLogs);
		});

		it("handles empty response from API", async () => {
			mockFetchLogsAPI([]);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() =>
					useSuspenseQuery(
						buildFilterLogsQuery({
							offset: 0,
							sort: "TIMESTAMP_ASC",
							limit: 100,
						}),
					),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual([]);
		});
	});
});
