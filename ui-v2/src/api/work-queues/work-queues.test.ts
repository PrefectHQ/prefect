import { createFakeWorkQueue } from "@/mocks";
import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { type WorkQueue, buildFilterWorkQueuesQuery } from "./work-queues";

describe("work queues api", () => {
	const mockFetchWorkQueuesAPI = (workPools: Array<WorkQueue>) => {
		server.use(
			http.post(buildApiUrl("/work_queues/filter"), () => {
				return HttpResponse.json(workPools);
			}),
		);
	};

	describe("buildFilterWorkPoolsQuery", () => {
		it("fetches filtered workpools", async () => {
			const workQueue = createFakeWorkQueue();
			mockFetchWorkQueuesAPI([workQueue]);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildFilterWorkQueuesQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual([workQueue]);
		});
	});
});
