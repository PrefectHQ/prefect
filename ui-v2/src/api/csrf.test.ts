import {
	afterEach,
	beforeEach,
	describe,
	expect,
	type MockInstance,
	test,
	vi,
} from "vitest";
import { csrfMiddleware, csrfTokenManager } from "./csrf";
import { uiSettings } from "./ui-settings";

const MOCK_CSRF_TOKEN_RESPONSE = {
	id: "csrf-token-id",
	created: new Date().toISOString(),
	updated: new Date().toISOString(),
	token: "test-csrf-token-value",
	client: "test-client-id",
	expiration: new Date(Date.now() + 3600000).toISOString(),
};

function mockUiSettings(csrfEnabled: boolean) {
	vi.spyOn(uiSettings, "load").mockResolvedValue({
		apiUrl: "http://localhost:4200/api",
		csrfEnabled,
		auth: null,
		flags: [],
	});
	vi.spyOn(uiSettings, "getApiUrl").mockResolvedValue(
		"http://localhost:4200/api",
	);
}

function mockFetchCsrfToken(fetchSpy: MockInstance) {
	fetchSpy.mockImplementation((input: RequestInfo | URL) => {
		const url =
			typeof input === "string"
				? input
				: input instanceof URL
					? input.href
					: input.url;
		if (url.includes("/csrf-token")) {
			return Promise.resolve({
				ok: true,
				json: () => Promise.resolve(MOCK_CSRF_TOKEN_RESPONSE),
			} as Response);
		}
		return Promise.resolve({ ok: false, status: 404 } as Response);
	});
}

describe("CsrfTokenManager", () => {
	let fetchSpy: MockInstance;

	beforeEach(() => {
		csrfTokenManager.reset();
		uiSettings.reset();
		fetchSpy = vi.spyOn(globalThis, "fetch");
		vi.useFakeTimers({ shouldAdvanceTime: true });
	});

	afterEach(() => {
		csrfTokenManager.reset();
		uiSettings.reset();
		vi.restoreAllMocks();
		vi.useRealTimers();
	});

	test("addCsrfHeaders does nothing when CSRF is disabled", async () => {
		mockUiSettings(false);

		const request = new Request("http://localhost:4200/api/flow_runs/count", {
			method: "POST",
		});

		const result = await csrfTokenManager.addCsrfHeaders(request);

		expect(result).toBe(false);
		expect(request.headers.has("Prefect-Csrf-Token")).toBe(false);
		expect(request.headers.has("Prefect-Csrf-Client")).toBe(false);
		expect(fetchSpy).not.toHaveBeenCalled();
	});

	test("addCsrfHeaders fetches token and sets headers when CSRF is enabled", async () => {
		mockUiSettings(true);
		mockFetchCsrfToken(fetchSpy);

		const request = new Request("http://localhost:4200/api/flow_runs/count", {
			method: "POST",
		});

		const result = await csrfTokenManager.addCsrfHeaders(request);

		expect(result).toBe(true);
		expect(request.headers.get("Prefect-Csrf-Token")).toBe(
			"test-csrf-token-value",
		);
		expect(request.headers.has("Prefect-Csrf-Client")).toBe(true);
	});

	test("addCsrfHeaders caches token across multiple calls", async () => {
		mockUiSettings(true);
		mockFetchCsrfToken(fetchSpy);

		const request1 = new Request("http://localhost:4200/api/flow_runs/count", {
			method: "POST",
		});
		const request2 = new Request("http://localhost:4200/api/flow_runs/filter", {
			method: "POST",
		});

		await csrfTokenManager.addCsrfHeaders(request1);
		await csrfTokenManager.addCsrfHeaders(request2);

		// Only one fetch for the CSRF token endpoint
		const csrfFetchCalls = fetchSpy.mock.calls.filter((call) =>
			String(call[0]).includes("/csrf-token"),
		);
		expect(csrfFetchCalls).toHaveLength(1);

		expect(request1.headers.get("Prefect-Csrf-Token")).toBe(
			"test-csrf-token-value",
		);
		expect(request2.headers.get("Prefect-Csrf-Token")).toBe(
			"test-csrf-token-value",
		);
	});

	test("addCsrfHeaders deduplicates concurrent fetch requests", async () => {
		mockUiSettings(true);
		mockFetchCsrfToken(fetchSpy);

		const request1 = new Request("http://localhost:4200/api/test1", {
			method: "POST",
		});
		const request2 = new Request("http://localhost:4200/api/test2", {
			method: "POST",
		});

		await Promise.all([
			csrfTokenManager.addCsrfHeaders(request1),
			csrfTokenManager.addCsrfHeaders(request2),
		]);

		const csrfFetchCalls = fetchSpy.mock.calls.filter((call) =>
			String(call[0]).includes("/csrf-token"),
		);
		expect(csrfFetchCalls).toHaveLength(1);
	});

	test("refreshToken forces a new token fetch", async () => {
		mockUiSettings(true);
		mockFetchCsrfToken(fetchSpy);

		// Initial fetch
		const request = new Request("http://localhost:4200/api/test", {
			method: "POST",
		});
		await csrfTokenManager.addCsrfHeaders(request);

		// Force refresh
		await csrfTokenManager.refreshToken();

		const csrfFetchCalls = fetchSpy.mock.calls.filter((call) =>
			String(call[0]).includes("/csrf-token"),
		);
		expect(csrfFetchCalls).toHaveLength(2);
	});

	test("fetches a new token when the current one is expired", async () => {
		mockUiSettings(true);

		// First call: return token that expires immediately
		const expiredToken = {
			...MOCK_CSRF_TOKEN_RESPONSE,
			expiration: new Date(Date.now() - 1000).toISOString(),
		};
		fetchSpy
			.mockResolvedValueOnce({
				ok: true,
				json: () => Promise.resolve(expiredToken),
			} as Response)
			.mockResolvedValueOnce({
				ok: true,
				json: () => Promise.resolve(MOCK_CSRF_TOKEN_RESPONSE),
			} as Response);

		const request1 = new Request("http://localhost:4200/api/test", {
			method: "POST",
		});
		await csrfTokenManager.addCsrfHeaders(request1);

		const request2 = new Request("http://localhost:4200/api/test", {
			method: "POST",
		});
		await csrfTokenManager.addCsrfHeaders(request2);

		const csrfFetchCalls = fetchSpy.mock.calls.filter((call) =>
			String(call[0]).includes("/csrf-token"),
		);
		expect(csrfFetchCalls).toHaveLength(2);
	});

	test("includes auth header when password is stored", async () => {
		mockUiSettings(true);
		mockFetchCsrfToken(fetchSpy);

		vi.spyOn(localStorage, "getItem").mockReturnValue("test-password");

		const request = new Request("http://localhost:4200/api/test", {
			method: "POST",
		});
		await csrfTokenManager.addCsrfHeaders(request);

		const csrfFetchCall = fetchSpy.mock.calls.find((call) =>
			String(call[0]).includes("/csrf-token"),
		);
		expect(csrfFetchCall).toBeDefined();
		const fetchOptions = csrfFetchCall?.[1] as RequestInit;
		expect((fetchOptions.headers as Record<string, string>).Authorization).toBe(
			"Basic test-password",
		);
	});

	test("reset clears all state", async () => {
		mockUiSettings(true);
		mockFetchCsrfToken(fetchSpy);

		const request = new Request("http://localhost:4200/api/test", {
			method: "POST",
		});
		await csrfTokenManager.addCsrfHeaders(request);

		csrfTokenManager.reset();

		const request2 = new Request("http://localhost:4200/api/test", {
			method: "POST",
		});
		await csrfTokenManager.addCsrfHeaders(request2);

		const csrfFetchCalls = fetchSpy.mock.calls.filter((call) =>
			String(call[0]).includes("/csrf-token"),
		);
		expect(csrfFetchCalls).toHaveLength(2);
	});
});

describe("csrfMiddleware", () => {
	let fetchSpy: MockInstance;

	beforeEach(() => {
		csrfTokenManager.reset();
		uiSettings.reset();
		fetchSpy = vi.spyOn(globalThis, "fetch");
		vi.useFakeTimers({ shouldAdvanceTime: true });
	});

	afterEach(() => {
		csrfTokenManager.reset();
		uiSettings.reset();
		vi.restoreAllMocks();
		vi.useRealTimers();
	});

	test("attaches CSRF headers to POST requests when enabled", async () => {
		mockUiSettings(true);
		mockFetchCsrfToken(fetchSpy);

		const request = new Request("http://localhost:4200/api/flow_runs/count", {
			method: "POST",
		});

		const result = await csrfMiddleware.onRequest?.({
			request,
			schemaPath: "/flow_runs/count",
			params: {},
			id: "test",
		});

		expect((result as Request).headers.get("Prefect-Csrf-Token")).toBe(
			"test-csrf-token-value",
		);
	});

	test("attaches CSRF headers to PUT requests when enabled", async () => {
		mockUiSettings(true);
		mockFetchCsrfToken(fetchSpy);

		const request = new Request("http://localhost:4200/api/variables/123", {
			method: "PUT",
		});

		const result = await csrfMiddleware.onRequest?.({
			request,
			schemaPath: "/variables/{id}",
			params: {},
			id: "test",
		});

		expect((result as Request).headers.get("Prefect-Csrf-Token")).toBe(
			"test-csrf-token-value",
		);
	});

	test("attaches CSRF headers to PATCH requests when enabled", async () => {
		mockUiSettings(true);
		mockFetchCsrfToken(fetchSpy);

		const request = new Request("http://localhost:4200/api/variables/123", {
			method: "PATCH",
		});

		const result = await csrfMiddleware.onRequest?.({
			request,
			schemaPath: "/variables/{id}",
			params: {},
			id: "test",
		});

		expect((result as Request).headers.get("Prefect-Csrf-Token")).toBe(
			"test-csrf-token-value",
		);
	});

	test("attaches CSRF headers to DELETE requests when enabled", async () => {
		mockUiSettings(true);
		mockFetchCsrfToken(fetchSpy);

		const request = new Request("http://localhost:4200/api/flow_runs/123", {
			method: "DELETE",
		});

		const result = await csrfMiddleware.onRequest?.({
			request,
			schemaPath: "/flow_runs/{id}",
			params: {},
			id: "test",
		});

		expect((result as Request).headers.get("Prefect-Csrf-Token")).toBe(
			"test-csrf-token-value",
		);
	});

	test("does not attach CSRF headers to GET requests", async () => {
		mockUiSettings(true);
		mockFetchCsrfToken(fetchSpy);

		const request = new Request("http://localhost:4200/api/flows/123", {
			method: "GET",
		});

		const result = await csrfMiddleware.onRequest?.({
			request,
			schemaPath: "/flows/{id}",
			params: {},
			id: "test",
		});

		expect((result as Request).headers.has("Prefect-Csrf-Token")).toBe(false);
		expect((result as Request).headers.has("Prefect-Csrf-Client")).toBe(false);
	});

	test("does not attach CSRF headers when CSRF is disabled", async () => {
		mockUiSettings(false);

		const request = new Request("http://localhost:4200/api/flow_runs/count", {
			method: "POST",
		});

		const result = await csrfMiddleware.onRequest?.({
			request,
			schemaPath: "/flow_runs/count",
			params: {},
			id: "test",
		});

		expect((result as Request).headers.has("Prefect-Csrf-Token")).toBe(false);
	});
});
