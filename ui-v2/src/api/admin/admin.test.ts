import { useSuspenseQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { expect, test } from "vitest";
import { createFakeServerSettings, createFakeVersion } from "@/mocks";

import {
	buildGetDefaultResultStorageQuery,
	buildGetSettingsQuery,
	buildGetVersionQuery,
	useClearDefaultResultStorage,
	useUpdateDefaultResultStorage,
} from "./admin";

test("buildGetVersionQuery -- fetches version query from API", async () => {
	const MOCK_VERSION = createFakeVersion();

	// SETUP
	server.use(
		http.get(buildApiUrl("/admin/version"), () => {
			return HttpResponse.json(MOCK_VERSION);
		}),
	);

	// TEST
	const { result } = renderHook(
		() => useSuspenseQuery(buildGetVersionQuery()),
		{ wrapper: createWrapper() },
	);

	await waitFor(() => expect(result.current.isSuccess).toBe(true));
	expect(result.current.data).toEqual(MOCK_VERSION);
});

test("buildSettingsQuery -- fetches version query from API", async () => {
	const MOCK_SETTINGS_RESPONSE = createFakeServerSettings();

	// SETUP
	server.use(
		http.get(buildApiUrl("/admin/settings"), () => {
			return HttpResponse.json(MOCK_SETTINGS_RESPONSE);
		}),
	);

	// TEST
	const { result } = renderHook(
		() => useSuspenseQuery(buildGetSettingsQuery()),
		{ wrapper: createWrapper() },
	);

	await waitFor(() => expect(result.current.isSuccess).toBe(true));
	expect(result.current.data).toEqual(MOCK_SETTINGS_RESPONSE);
});

test("buildGetDefaultResultStorageQuery -- fetches default result storage from API", async () => {
	const MOCK_STORAGE_RESPONSE = {
		default_result_storage_block_id: "e8607583-f98e-48c5-bb49-6f031d7bff12",
	};

	server.use(
		http.get(buildApiUrl("/admin/storage"), () => {
			return HttpResponse.json(MOCK_STORAGE_RESPONSE);
		}),
	);

	const { result } = renderHook(
		() => useSuspenseQuery(buildGetDefaultResultStorageQuery()),
		{ wrapper: createWrapper() },
	);

	await waitFor(() => expect(result.current.isSuccess).toBe(true));
	expect(result.current.data).toEqual(MOCK_STORAGE_RESPONSE);
});

test("useUpdateDefaultResultStorage -- updates default result storage through API", async () => {
	const MOCK_STORAGE_RESPONSE = {
		default_result_storage_block_id: "e8607583-f98e-48c5-bb49-6f031d7bff12",
	};

	server.use(
		http.put(buildApiUrl("/admin/storage"), async ({ request }) => {
			expect(await request.json()).toEqual(MOCK_STORAGE_RESPONSE);
			return HttpResponse.json(MOCK_STORAGE_RESPONSE);
		}),
	);

	const { result } = renderHook(useUpdateDefaultResultStorage, {
		wrapper: createWrapper(),
	});

	act(() => {
		result.current.updateDefaultResultStorage(MOCK_STORAGE_RESPONSE);
	});

	await waitFor(() => expect(result.current.isSuccess).toBe(true));
});

test("useClearDefaultResultStorage -- clears default result storage through API", async () => {
	server.use(
		http.delete(buildApiUrl("/admin/storage"), () => {
			return new HttpResponse(null, { status: 204 });
		}),
	);

	const { result } = renderHook(useClearDefaultResultStorage, {
		wrapper: createWrapper(),
	});

	act(() => {
		result.current.clearDefaultResultStorage();
	});

	await waitFor(() => expect(result.current.isSuccess).toBe(true));
});
