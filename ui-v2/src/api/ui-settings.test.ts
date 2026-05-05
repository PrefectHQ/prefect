import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { resolveUiSettingsBaseUrl, uiSettings } from "./ui-settings";

describe("UiSettingsService", () => {
	const mockUiSettingsResponse = {
		api_url: "http://127.0.0.1:4200/api",
		csrf_enabled: false,
		auth: null,
		flags: ["feature-1", "feature-2"],
		default_ui: "v1",
		available_uis: ["v1", "v2"],
		v1_base_url: "/",
		v2_base_url: "/v2",
	};

	beforeEach(() => {
		uiSettings.reset();
		vi.restoreAllMocks();
	});

	afterEach(() => {
		uiSettings.reset();
	});

	test("load() fetches settings from /ui-settings endpoint", async () => {
		const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
			ok: true,
			json: () => Promise.resolve(mockUiSettingsResponse),
		} as Response);

		const settings = await uiSettings.load();

		expect(fetchSpy).toHaveBeenCalledTimes(1);
		expect(fetchSpy).toHaveBeenCalledWith(
			expect.stringContaining("/ui-settings"),
		);
		expect(settings).toEqual({
			apiUrl: "http://127.0.0.1:4200/api",
			csrfEnabled: false,
			auth: null,
			flags: ["feature-1", "feature-2"],
			defaultUi: "v1",
			availableUis: ["v1", "v2"],
			v1BaseUrl: "/",
			v2BaseUrl: "/v2",
		});
	});

	test("load() caches settings after first fetch", async () => {
		const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
			ok: true,
			json: () => Promise.resolve(mockUiSettingsResponse),
		} as Response);

		// First call should fetch
		const settings1 = await uiSettings.load();
		// Second call should use cache
		const settings2 = await uiSettings.load();

		expect(fetchSpy).toHaveBeenCalledTimes(1);
		expect(settings1).toEqual(settings2);
	});

	test("load() handles concurrent calls with single fetch", async () => {
		const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
			ok: true,
			json: () => Promise.resolve(mockUiSettingsResponse),
		} as Response);

		// Make concurrent calls
		const [settings1, settings2, settings3] = await Promise.all([
			uiSettings.load(),
			uiSettings.load(),
			uiSettings.load(),
		]);

		// Should only fetch once despite concurrent calls
		expect(fetchSpy).toHaveBeenCalledTimes(1);
		expect(settings1).toEqual(settings2);
		expect(settings2).toEqual(settings3);
	});

	test("load() throws error on non-ok response", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
			ok: false,
			status: 500,
		} as Response);

		await expect(uiSettings.load()).rejects.toThrow(
			"Prefect server error: The server returned an error (500). This may be a temporary issue.",
		);
	});

	test("load() handles null flags in response", async () => {
		const responseWithNullFlags = {
			api_url: "http://127.0.0.1:4200/api",
			csrf_enabled: true,
			auth: "oauth2",
			flags: null,
			default_ui: "v2",
			available_uis: ["v2"],
			v1_base_url: null,
			v2_base_url: "/v2",
		};

		vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
			ok: true,
			json: () => Promise.resolve(responseWithNullFlags),
		} as Response);

		const settings = await uiSettings.load();

		expect(settings.flags).toEqual([]);
		expect(settings.defaultUi).toBe("v2");
		expect(settings.availableUis).toEqual(["v2"]);
	});

	test("getApiUrl() returns the api_url from settings", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
			ok: true,
			json: () => Promise.resolve(mockUiSettingsResponse),
		} as Response);

		const apiUrl = await uiSettings.getApiUrl();

		expect(apiUrl).toBe("http://127.0.0.1:4200/api");
	});

	test("reset() clears cached settings", async () => {
		const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
			ok: true,
			json: () => Promise.resolve(mockUiSettingsResponse),
		} as Response);

		// First load
		await uiSettings.load();
		expect(fetchSpy).toHaveBeenCalledTimes(1);

		// Reset and load again
		uiSettings.reset();
		await uiSettings.load();

		// Should fetch again after reset
		expect(fetchSpy).toHaveBeenCalledTimes(2);
	});

	test("load() transforms snake_case response to camelCase", async () => {
		const snakeCaseResponse = {
			api_url: "http://test.example.com/api",
			csrf_enabled: true,
			auth: "bearer",
			flags: ["flag-a"],
			default_ui: "v1",
			available_uis: ["v1"],
			v1_base_url: "/",
			v2_base_url: null,
		};

		vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
			ok: true,
			json: () => Promise.resolve(snakeCaseResponse),
		} as Response);

		const settings = await uiSettings.load();

		expect(settings).toEqual({
			apiUrl: "http://test.example.com/api",
			csrfEnabled: true,
			auth: "bearer",
			flags: ["flag-a"],
			defaultUi: "v1",
			availableUis: ["v1"],
			v1BaseUrl: "/",
			v2BaseUrl: null,
		});
	});

	test("resolveUiSettingsBaseUrl preserves runtime proxy prefixes", () => {
		expect(
			resolveUiSettingsBaseUrl({
				appBasePath: "/prefect/v2",
				pathname: "/proxy/prefect/v2/dashboard",
			}),
		).toBe("/proxy/prefect");
		expect(
			resolveUiSettingsBaseUrl({
				appBasePath: "/v2",
				pathname: "/proxy/v2/dashboard",
			}),
		).toBe("/proxy");
		expect(
			resolveUiSettingsBaseUrl({
				appBasePath: "/v2",
				pathname: "/company/v2/prefect/v2/settings",
			}),
		).toBe("/company/v2/prefect");
	});
});
