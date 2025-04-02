import { QueryClient } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { buildApiUrl, createWrapper, server } from "@tests/utils";
import {
	useDeleteWorkPool,
	usePauseWorkPool,
	useResumeWorkPool,
} from "./work-pools";

describe("work pool hooks", () => {
	const MOCK_WORK_POOL_NAME = "test-pool";

	/**
	 * Data Management:
	 * - Asserts pause mutation API is called
	 * - Upon pause mutation API being called, cache is invalidated
	 */
	it("usePauseWorkPool() invalidates cache", async () => {
		const queryClient = new QueryClient();

		// ------------ Mock API requests
		server.use(
			http.patch(buildApiUrl(`/work_pools/${MOCK_WORK_POOL_NAME}`), () => {
				return HttpResponse.json({});
			}),
		);

		// ------------ Initialize hooks to test
		const { result } = renderHook(usePauseWorkPool, {
			wrapper: createWrapper({ queryClient }),
		});

		// ------------ Invoke mutation
		act(() => result.current.pauseWorkPool(MOCK_WORK_POOL_NAME));

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
	});

	/**
	 * Data Management:
	 * - Asserts resume mutation API is called
	 * - Upon resume mutation API being called, cache is invalidated
	 */
	it("useResumeWorkPool() invalidates cache", async () => {
		const queryClient = new QueryClient();

		// ------------ Mock API requests
		server.use(
			http.patch(buildApiUrl(`/work_pools/${MOCK_WORK_POOL_NAME}`), () => {
				return HttpResponse.json({});
			}),
		);

		// ------------ Initialize hooks to test
		const { result } = renderHook(useResumeWorkPool, {
			wrapper: createWrapper({ queryClient }),
		});

		// ------------ Invoke mutation
		act(() => result.current.resumeWorkPool(MOCK_WORK_POOL_NAME));

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
	});

	/**
	 * Data Management:
	 * - Asserts delete mutation API is called
	 * - Upon delete mutation API being called, cache is invalidated
	 */
	it("useDeleteWorkPool() invalidates cache", async () => {
		const queryClient = new QueryClient();

		// ------------ Mock API requests
		server.use(
			http.delete(buildApiUrl(`/work_pools/${MOCK_WORK_POOL_NAME}`), () => {
				return HttpResponse.json({});
			}),
		);

		// ------------ Initialize hooks to test
		const { result } = renderHook(useDeleteWorkPool, {
			wrapper: createWrapper({ queryClient }),
		});

		// ------------ Invoke mutation
		act(() => result.current.deleteWorkPool(MOCK_WORK_POOL_NAME));

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
	});
});
