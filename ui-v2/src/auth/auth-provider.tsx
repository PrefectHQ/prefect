import { type ReactNode, useCallback, useEffect, useState } from "react";
import { uiSettings } from "@/api/ui-settings";
import { AuthContext, type AuthState } from "./auth-context";

const AUTH_STORAGE_KEY = "prefect-password";

async function validateCredentials(
	password: string,
	apiUrl: string,
): Promise<boolean> {
	try {
		const response = await fetch(`${apiUrl}/admin/version`, {
			headers: {
				Authorization: `Basic ${password}`,
			},
		});
		return response.ok;
	} catch {
		return false;
	}
}

export function AuthProvider({ children }: { children: ReactNode }) {
	const [isLoading, setIsLoading] = useState(true);
	const [isAuthenticated, setIsAuthenticated] = useState(false);
	const [authRequired, setAuthRequired] = useState(false);

	// Listen for 401 unauthorized events from API middleware
	useEffect(() => {
		const handleUnauthorized = () => {
			setIsAuthenticated(false);
		};

		window.addEventListener("auth:unauthorized", handleUnauthorized);
		return () =>
			window.removeEventListener("auth:unauthorized", handleUnauthorized);
	}, []);

	useEffect(() => {
		const initAuth = async () => {
			try {
				const settings = await uiSettings.load();
				const requiresAuth = settings.auth === "BASIC";
				setAuthRequired(requiresAuth);

				if (!requiresAuth) {
					setIsAuthenticated(true);
					setIsLoading(false);
					return;
				}

				const storedPassword = localStorage.getItem(AUTH_STORAGE_KEY);
				if (storedPassword) {
					const isValid = await validateCredentials(
						storedPassword,
						settings.apiUrl,
					);
					setIsAuthenticated(isValid);
					if (!isValid) {
						localStorage.removeItem(AUTH_STORAGE_KEY);
					}
				}
			} catch (error) {
				console.error("Failed to initialize auth:", error);
			} finally {
				setIsLoading(false);
			}
		};

		void initAuth();
	}, []);

	const login = useCallback(
		async (password: string): Promise<{ success: boolean; error?: string }> => {
			try {
				const settings = await uiSettings.load();
				const encodedPassword = btoa(password);
				const isValid = await validateCredentials(
					encodedPassword,
					settings.apiUrl,
				);

				if (isValid) {
					localStorage.setItem(AUTH_STORAGE_KEY, encodedPassword);
					setIsAuthenticated(true);
					return { success: true };
				}
				return { success: false, error: "Invalid credentials" };
			} catch {
				return { success: false, error: "Authentication failed" };
			}
		},
		[],
	);

	const logout = useCallback(() => {
		localStorage.removeItem(AUTH_STORAGE_KEY);
		setIsAuthenticated(false);
	}, []);

	const value: AuthState = {
		isAuthenticated,
		isLoading,
		authRequired,
		login,
		logout,
	};

	return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
