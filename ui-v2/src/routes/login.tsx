import { createFileRoute, Navigate, redirect } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { useAuthSafe } from "@/auth";
import { LoginPage } from "@/components/auth/login-page";
import { PrefectLoading } from "@/components/ui/loading";

const loginSearchSchema = z.object({
	redirectTo: z.string().optional(),
});

export const Route = createFileRoute("/login")({
	validateSearch: zodValidator(loginSearchSchema),
	beforeLoad: ({ context, search }) => {
		// If already authenticated, redirect away from login page
		if (!context.auth.isLoading && context.auth.isAuthenticated) {
			redirect({ to: search.redirectTo ?? "/dashboard", throw: true });
		}
	},
	component: function LoginRouteComponent() {
		const { redirectTo } = Route.useSearch();
		const auth = useAuthSafe();

		// If auth context is not available (e.g., in tests), just render the login page
		if (!auth) {
			return <LoginPage redirectTo={redirectTo} />;
		}

		// Show loading state while auth is initializing
		if (auth.isLoading) {
			return <PrefectLoading />;
		}

		// Redirect to dashboard if already authenticated
		// (This handles the case where beforeLoad didn't catch it due to loading state)
		if (auth.isAuthenticated) {
			return <Navigate to={redirectTo ?? "/dashboard"} replace={true} />;
		}

		return <LoginPage redirectTo={redirectTo} />;
	},
});
