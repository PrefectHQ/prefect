import { MainLayout } from "@/components/layouts/MainLayout";
import type { QueryClient } from "@tanstack/react-query";
import { Outlet, createRootRouteWithContext } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/router-devtools";

interface MyRouterContext {
	queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<MyRouterContext>()({
	component: () => (
		<MainLayout>
			<Outlet />
			<TanStackRouterDevtools />
		</MainLayout>
	),
});
