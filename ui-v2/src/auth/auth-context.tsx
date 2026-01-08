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
