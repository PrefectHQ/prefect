import type { QueryClient } from "@tanstack/react-query";
import type { ErrorComponentProps } from "@tanstack/react-router";
import {
	createRootRouteWithContext,
	Navigate,
	Outlet,
	redirect,
	useRouter,
	useRouterState,
} from "@tanstack/react-router";
import { lazy, Suspense, useCallback } from "react";
import { categorizeError } from "@/api/error-utils";
import { uiSettings } from "@/api/ui-settings";
import { type AuthState, useAuthSafe } from "@/auth";
import { MainLayout } from "@/components/layouts/MainLayout";
import { PrefectLoading } from "@/components/ui/loading";
import { ServerErrorDisplay } from "@/components/ui/server-error";

const showDevtools =
	import.meta.env.DEV && import.meta.env.VITE_DISABLE_DEVTOOLS !== "true";

const lazyDevtools = showDevtools
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
	component: function RootComponent() {
		const TanStackRouterDevtools = lazyDevtools;

		const location = useRouterState({ select: (s) => s.location });
		const auth = useAuthSafe();
		const isLoginPage = location.pathname === "/login";

		// If auth context is not available (e.g., in tests), skip auth checks
		if (auth) {
			// Show loading state while auth is initializing
			if (auth.isLoading) {
				return <PrefectLoading />;
			}

			// Redirect to login if auth is required and user is not authenticated
			// (This handles the case where beforeLoad didn't catch it due to loading state)
			if (auth.authRequired && !auth.isAuthenticated && !isLoginPage) {
				return (
					<Navigate
						to="/login"
						search={{ redirectTo: location.href }}
						replace={true}
					/>
				);
			}
		}

		const content = (
			<>
				<Outlet />
				{showDevtools && (
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
	},
	errorComponent: function RootErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const router = useRouter();
		const serverError = categorizeError(
			error,
			"Failed to initialize application",
		);

		const handleRetry = useCallback(() => {
			// Reset the ui-settings cached promise so it will retry on next load
			uiSettings.reset();
			// Reset the router error boundary to trigger re-render
			reset();
			// Invalidate the router to force loaders to re-run
			void router.invalidate();
		}, [reset, router]);

		return <ServerErrorDisplay error={serverError} onRetry={handleRetry} />;
	},
});
