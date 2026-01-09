import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
	AuthContext,
	type AuthState,
	useAuth,
	useAuthSafe,
} from "./auth-context";

describe("auth-context", () => {
	describe("useAuth", () => {
		it("throws error when used outside of AuthProvider", () => {
			expect(() => {
				renderHook(() => useAuth());
			}).toThrow("useAuth must be used within an AuthProvider");
		});

		it("returns context value when used inside AuthProvider", () => {
			const mockAuthState: AuthState = {
				isAuthenticated: true,
				isLoading: false,
				authRequired: true,
				login: vi.fn(),
				logout: vi.fn(),
			};

			const wrapper = ({ children }: { children: React.ReactNode }) => (
				<AuthContext.Provider value={mockAuthState}>
					{children}
				</AuthContext.Provider>
			);

			const { result } = renderHook(() => useAuth(), { wrapper });

			expect(result.current).toEqual(mockAuthState);
			expect(result.current.isAuthenticated).toBe(true);
			expect(result.current.isLoading).toBe(false);
			expect(result.current.authRequired).toBe(true);
		});
	});

	describe("useAuthSafe", () => {
		it("returns null when used outside of AuthProvider", () => {
			const { result } = renderHook(() => useAuthSafe());
			expect(result.current).toBeNull();
		});

		it("returns context value when used inside AuthProvider", () => {
			const mockAuthState: AuthState = {
				isAuthenticated: true,
				isLoading: false,
				authRequired: true,
				login: vi.fn(),
				logout: vi.fn(),
			};

			const wrapper = ({ children }: { children: React.ReactNode }) => (
				<AuthContext.Provider value={mockAuthState}>
					{children}
				</AuthContext.Provider>
			);

			const { result } = renderHook(() => useAuthSafe(), { wrapper });

			expect(result.current).toEqual(mockAuthState);
			expect(result.current?.isAuthenticated).toBe(true);
			expect(result.current?.isLoading).toBe(false);
			expect(result.current?.authRequired).toBe(true);
		});
	});
});
