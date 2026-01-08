import type { QueryClient } from "@tanstack/react-query";
import type { ErrorComponentProps } from "@tanstack/react-router";
import {
	createRootRouteWithContext,
	Outlet,
	redirect,
	useRouterState,
} from "@tanstack/react-router";
import { lazy, Suspense, useCallback } from "react";
import { categorizeError } from "@/api/error-utils";
import { uiSettings } from "@/api/ui-settings";
import type { AuthState } from "@/auth";
import { MainLayout } from "@/components/layouts/MainLayout";
import { ServerErrorDisplay } from "@/components/ui/server-error";

const TanStackRouterDevtools = import.meta.env.DEV
	? lazy(() =>
			import("@tanstack/router-devtools").then((mod) => ({
				default: mod.TanStackRouterDevtools,
			})),
		)
	: () => null;

interface MyRouterContext {
	queryClient: QueryClient;
	auth: AuthState;
}

function RootErrorComponent({ error, reset }: ErrorComponentProps) {
	const serverError = categorizeError(
		error,
		"Failed to initialize application",
	);

	const handleRetry = useCallback(() => {
		// Reset the ui-settings cached promise so it will retry on next load
		uiSettings.reset();
		// Reset the router error boundary to trigger re-render
		reset();
	}, [reset]);

	return <ServerErrorDisplay error={serverError} onRetry={handleRetry} />;
}

function RootComponent() {
	const location = useRouterState({ select: (s) => s.location });
	const isLoginPage = location.pathname === "/login";

	const content = (
		<>
			<Outlet />
			{import.meta.env.DEV && (
				<Suspense fallback={null}>
					<TanStackRouterDevtools />
				</Suspense>
			)}
		</>
	);

	// Don't show sidebar/layout on login page
	if (isLoginPage) {
		return content;
	}

	return <MainLayout>{content}</MainLayout>;
}

export const Route = createRootRouteWithContext<MyRouterContext>()({
	beforeLoad: ({ context, location }) => {
		// Skip auth check for login route or if auth context is not available (e.g., in tests)
		if (location.pathname === "/login" || !context.auth) {
			return;
		}

		// Wait for auth to finish loading
		if (context.auth.isLoading) {
			return;
		}

		// If auth is required and user is not authenticated, redirect to login
		if (context.auth.authRequired && !context.auth.isAuthenticated) {
			redirect({
				to: "/login",
				search: {
					redirectTo: location.href,
				},
				throw: true,
			});
		}
	},
	component: RootComponent,
	errorComponent: RootErrorComponent,
});
