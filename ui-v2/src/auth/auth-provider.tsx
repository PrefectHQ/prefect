import { type ReactNode, useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { uiSettings } from "@/api/ui-settings";
import { AuthContext, type AuthState } from "./auth-context";

const AUTH_STORAGE_KEY = "prefect-password";

type ValidationResult = {
	valid: boolean;
	unauthorized: boolean;
};

async function validateCredentials(
	password: string,
	apiUrl: string,
): Promise<ValidationResult> {
	try {
		const response = await fetch(`${apiUrl}/admin/version`, {
			headers: {
				Authorization: `Basic ${password}`,
			},
		});
		return { valid: response.ok, unauthorized: response.status === 401 };
	} catch {
		return { valid: false, unauthorized: false };
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
			toast.error("Authentication failed.", {
				duration: Number.POSITIVE_INFINITY,
				id: "auth-failed",
			});
		};

		window.addEventListener("auth:unauthorized", handleUnauthorized);
		return () =>
			window.removeEventListener("auth:unauthorized", handleUnauthorized);
	}, []);

	useEffect(() => {
		const initAuth = async () => {
			try {
				const settings = await uiSettings.load();
				const requiresAuth = Boolean(settings.auth);
				setAuthRequired(requiresAuth);

				if (!requiresAuth) {
					setIsAuthenticated(true);
					setIsLoading(false);
					return;
				}

				const storedPassword = localStorage.getItem(AUTH_STORAGE_KEY);
				if (storedPassword) {
					const result = await validateCredentials(
						storedPassword,
						settings.apiUrl,
					);
					setIsAuthenticated(result.valid);
					if (!result.valid) {
						localStorage.removeItem(AUTH_STORAGE_KEY);
						if (result.unauthorized) {
							toast.error("Authentication failed.", {
								duration: Number.POSITIVE_INFINITY,
								id: "auth-failed",
							});
						}
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
				const result = await validateCredentials(
					encodedPassword,
					settings.apiUrl,
				);

				if (result.valid) {
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
