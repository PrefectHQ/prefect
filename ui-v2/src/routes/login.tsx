import { createFileRoute, Navigate, redirect } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { useAuth } from "@/auth";
import { LoginPage } from "@/components/auth/login-page";

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
	component: LoginRouteComponent,
});

function LoginRouteComponent() {
	const { redirectTo } = Route.useSearch();
	const auth = useAuth();

	// Show loading state while auth is initializing
	if (auth.isLoading) {
		return (
			<div className="flex h-screen w-screen items-center justify-center">
				<div className="text-muted-foreground">Loading...</div>
			</div>
		);
	}

	// Redirect to dashboard if already authenticated
	// (This handles the case where beforeLoad didn't catch it due to loading state)
	if (auth.isAuthenticated) {
		return <Navigate to={redirectTo ?? "/dashboard"} replace={true} />;
	}

	return <LoginPage redirectTo={redirectTo} />;
}
