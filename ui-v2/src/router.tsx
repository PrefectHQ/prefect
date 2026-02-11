import { QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";
import type { AuthState } from "@/auth";
// Import the generated route tree
import { routeTree } from "./routeTree.gen";

export const queryClient = new QueryClient();

export interface RouterContext {
	queryClient: QueryClient;
	auth: AuthState;
}

export const router = createRouter({
	routeTree,
	context: {
		queryClient: queryClient,
		auth: undefined as unknown as AuthState, // Will be provided by App
	},
	defaultPreload: "intent",
	// Since we're using React Query, we don't want loader calls to ever be stale
	// This will ensure that the loader is always called when the route is preloaded or visited
	defaultPreloadStaleTime: 0,
	// Show pending component after 400ms of loading, and keep it visible for at least 400ms
	defaultPendingMs: 400,
	defaultPendingMinMs: 400,
});

declare module "@tanstack/react-router" {
	interface Register {
		router: typeof router;
	}
}
