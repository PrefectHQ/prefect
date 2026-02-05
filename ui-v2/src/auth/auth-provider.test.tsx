/* eslint-disable @typescript-eslint/unbound-method */
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { uiSettings } from "@/api/ui-settings";
import { useAuth } from "./auth-context";
import { AuthProvider } from "./auth-provider";

vi.mock("@/api/ui-settings", () => ({
	uiSettings: {
		load: vi.fn(),
	},
}));

const AUTH_STORAGE_KEY = "prefect-password";

describe("AuthProvider", () => {
	let localStorageStore: Record<string, string> = {};

	beforeEach(() => {
		vi.clearAllMocks();
		localStorageStore = {};

		vi.mocked(localStorage.getItem).mockImplementation(
			(key: string) => localStorageStore[key] ?? null,
		);
		vi.mocked(localStorage.setItem).mockImplementation(
			(key: string, value: string) => {
				localStorageStore[key] = value;
			},
		);
		vi.mocked(localStorage.removeItem).mockImplementation((key: string) => {
			delete localStorageStore[key];
		});
		vi.mocked(localStorage.clear).mockImplementation(() => {
			localStorageStore = {};
		});
	});

	afterEach(() => {
		localStorageStore = {};
	});

	const wrapper = ({ children }: { children: React.ReactNode }) => (
		<AuthProvider>{children}</AuthProvider>
	);

	describe("initialization", () => {
		it("sets isAuthenticated to true when auth is not required", async () => {
			vi.mocked(uiSettings.load).mockResolvedValueOnce({
				apiUrl: "http://localhost:4200/api",
				csrfEnabled: false,
				auth: null,
				flags: [],
			});

			const { result } = renderHook(() => useAuth(), { wrapper });

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			expect(result.current.isAuthenticated).toBe(true);
			expect(result.current.authRequired).toBe(false);
		});

		it("sets authRequired to true when auth is BASIC", async () => {
			vi.mocked(uiSettings.load).mockResolvedValueOnce({
				apiUrl: "http://localhost:4200/api",
				csrfEnabled: false,
				auth: "BASIC",
				flags: [],
			});

			const { result } = renderHook(() => useAuth(), { wrapper });

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			expect(result.current.authRequired).toBe(true);
			expect(result.current.isAuthenticated).toBe(false);
		});

		it("validates stored credentials on init when auth is required", async () => {
			const encodedPassword = btoa("test-password");
			localStorageStore[AUTH_STORAGE_KEY] = encodedPassword;

			vi.mocked(uiSettings.load).mockResolvedValue({
				apiUrl: "http://localhost:4200/api",
				csrfEnabled: false,
				auth: "BASIC",
				flags: [],
			});

			const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
				ok: true,
			} as Response);

			const { result } = renderHook(() => useAuth(), { wrapper });

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			expect(fetchSpy).toHaveBeenCalledWith(
				"http://localhost:4200/api/admin/version",
				expect.objectContaining({
					headers: {
						Authorization: `Basic ${encodedPassword}`,
					},
				}),
			);
			expect(result.current.isAuthenticated).toBe(true);
		});

		it("removes invalid stored credentials on init", async () => {
			const encodedPassword = btoa("invalid-password");
			localStorageStore[AUTH_STORAGE_KEY] = encodedPassword;

			vi.mocked(uiSettings.load).mockResolvedValue({
				apiUrl: "http://localhost:4200/api",
				csrfEnabled: false,
				auth: "BASIC",
				flags: [],
			});

			vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
				ok: false,
				status: 401,
			} as Response);

			const { result } = renderHook(() => useAuth(), { wrapper });

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			expect(result.current.isAuthenticated).toBe(false);
			expect(localStorageStore[AUTH_STORAGE_KEY]).toBeUndefined();
		});

		it("handles errors during initialization gracefully", async () => {
			vi.mocked(uiSettings.load).mockRejectedValueOnce(
				new Error("Network error"),
			);

			const consoleSpy = vi
				.spyOn(console, "error")
				.mockImplementation(() => {});

			const { result } = renderHook(() => useAuth(), { wrapper });

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			expect(consoleSpy).toHaveBeenCalledWith(
				"Failed to initialize auth:",
				expect.any(Error),
			);
			consoleSpy.mockRestore();
		});
	});

	describe("login", () => {
		it("stores credentials and sets isAuthenticated on successful login", async () => {
			vi.mocked(uiSettings.load).mockResolvedValue({
				apiUrl: "http://localhost:4200/api",
				csrfEnabled: false,
				auth: "BASIC",
				flags: [],
			});

			vi.spyOn(globalThis, "fetch").mockResolvedValue({
				ok: true,
			} as Response);

			const { result } = renderHook(() => useAuth(), { wrapper });

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			let loginResult: { success: boolean; error?: string } | undefined;
			await act(async () => {
				loginResult = await result.current.login("my-password");
			});

			expect(loginResult?.success).toBe(true);
			expect(result.current.isAuthenticated).toBe(true);
			expect(localStorageStore[AUTH_STORAGE_KEY]).toBe(btoa("my-password"));
		});

		it("returns error on invalid credentials", async () => {
			vi.mocked(uiSettings.load).mockResolvedValue({
				apiUrl: "http://localhost:4200/api",
				csrfEnabled: false,
				auth: "BASIC",
				flags: [],
			});

			vi.spyOn(globalThis, "fetch").mockResolvedValue({
				ok: false,
				status: 401,
			} as Response);

			const { result } = renderHook(() => useAuth(), { wrapper });

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			let loginResult: { success: boolean; error?: string } | undefined;
			await act(async () => {
				loginResult = await result.current.login("wrong-password");
			});

			expect(loginResult?.success).toBe(false);
			expect(loginResult?.error).toBe("Invalid credentials");
			expect(result.current.isAuthenticated).toBe(false);
			expect(localStorageStore[AUTH_STORAGE_KEY]).toBeUndefined();
		});

		it("returns error when login throws", async () => {
			vi.mocked(uiSettings.load).mockResolvedValueOnce({
				apiUrl: "http://localhost:4200/api",
				csrfEnabled: false,
				auth: "BASIC",
				flags: [],
			});

			const { result } = renderHook(() => useAuth(), { wrapper });

			await waitFor(() => {
				expect(result.current.isLoading).toBe(false);
			});

			vi.mocked(uiSettings.load).mockRejectedValueOnce(
				new Error("Network error"),
			);

			let loginResult: { success: boolean; error?: string } | undefined;
			await act(async () => {
				loginResult = await result.current.login("password");
			});

			expect(loginResult?.success).toBe(false);
			expect(loginResult?.error).toBe("Authentication failed");
		});
	});

	describe("logout", () => {
		it("removes credentials and sets isAuthenticated to false", async () => {
			const encodedPassword = btoa("test-password");
			localStorageStore[AUTH_STORAGE_KEY] = encodedPassword;

			vi.mocked(uiSettings.load).mockResolvedValue({
				apiUrl: "http://localhost:4200/api",
				csrfEnabled: false,
				auth: "BASIC",
				flags: [],
			});

			vi.spyOn(globalThis, "fetch").mockResolvedValue({
				ok: true,
			} as Response);

			const { result } = renderHook(() => useAuth(), { wrapper });

			await waitFor(() => {
				expect(result.current.isAuthenticated).toBe(true);
			});

			act(() => {
				result.current.logout();
			});

			expect(result.current.isAuthenticated).toBe(false);
			expect(localStorageStore[AUTH_STORAGE_KEY]).toBeUndefined();
		});
	});

	describe("auth:unauthorized event", () => {
		it("sets isAuthenticated to false when auth:unauthorized event is dispatched", async () => {
			const encodedPassword = btoa("test-password");
			localStorageStore[AUTH_STORAGE_KEY] = encodedPassword;

			vi.mocked(uiSettings.load).mockResolvedValue({
				apiUrl: "http://localhost:4200/api",
				csrfEnabled: false,
				auth: "BASIC",
				flags: [],
			});

			vi.spyOn(globalThis, "fetch").mockResolvedValue({
				ok: true,
			} as Response);

			const { result } = renderHook(() => useAuth(), { wrapper });

			await waitFor(() => {
				expect(result.current.isAuthenticated).toBe(true);
			});

			act(() => {
				window.dispatchEvent(new CustomEvent("auth:unauthorized"));
			});

			expect(result.current.isAuthenticated).toBe(false);
		});

		it("cleans up event listener on unmount", async () => {
			vi.mocked(uiSettings.load).mockResolvedValue({
				apiUrl: "http://localhost:4200/api",
				csrfEnabled: false,
				auth: null,
				flags: [],
			});

			const removeEventListenerSpy = vi.spyOn(window, "removeEventListener");

			const { unmount } = renderHook(() => useAuth(), { wrapper });

			await waitFor(() => {
				expect(removeEventListenerSpy).not.toHaveBeenCalledWith(
					"auth:unauthorized",
					expect.any(Function),
				);
			});

			unmount();

			expect(removeEventListenerSpy).toHaveBeenCalledWith(
				"auth:unauthorized",
				expect.any(Function),
			);

			removeEventListenerSpy.mockRestore();
		});
	});
});
