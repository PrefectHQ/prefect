import type { QueryClient } from "@tanstack/react-query";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { createRootRouteWithContext, Outlet } from "@tanstack/react-router";
import { lazy, Suspense, useCallback } from "react";
import { categorizeError } from "@/api/error-utils";
import { uiSettings } from "@/api/ui-settings";
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

export const Route = createRootRouteWithContext<MyRouterContext>()({
	component: () => (
		<MainLayout>
			<Outlet />
			{import.meta.env.DEV && (
				<Suspense fallback={null}>
					<TanStackRouterDevtools />
				</Suspense>
			)}
		</MainLayout>
	),
	errorComponent: RootErrorComponent,
});
