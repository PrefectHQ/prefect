import { useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { expect, test } from "vitest";
import { createFakeServerSettings, createFakeVersion } from "@/mocks";

import { buildGetSettingsQuery, buildGetVersionQuery } from "./admin";

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
