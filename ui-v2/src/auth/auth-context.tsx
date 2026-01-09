import { createContext, useContext } from "react";

export interface AuthState {
	isAuthenticated: boolean;
	isLoading: boolean;
	authRequired: boolean;
	login: (password: string) => Promise<{ success: boolean; error?: string }>;
	logout: () => void;
}

export const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
	const context = useContext(AuthContext);
	if (!context) {
		throw new Error("useAuth must be used within an AuthProvider");
	}
	return context;
}

/**
 * Safe version of useAuth that returns null when not in an AuthProvider.
 * Use this in components that may be rendered outside of the auth context (e.g., in tests).
 */
export function useAuthSafe(): AuthState | null {
	return useContext(AuthContext);
}
