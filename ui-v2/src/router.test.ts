import {
	createMemoryHistory,
	createRootRoute,
	createRoute,
	createRouter,
} from "@tanstack/react-router";
import { describe, expect, it } from "vitest";
import { resolveRouterBasePath } from "./router";

describe("router basepath", () => {
	it("prefixes built hrefs when the app is served from /v2", () => {
		const rootRoute = createRootRoute();
		const settingsRoute = createRoute({
			getParentRoute: () => rootRoute,
			path: "/settings",
			component: () => null,
		});
		const routeTree = rootRoute.addChildren([settingsRoute]);
		const router = createRouter({
			routeTree,
			basepath: resolveRouterBasePath({
				appBasePath: "/v2/",
				pathname: "/v2/settings",
			}),
			history: createMemoryHistory({
				initialEntries: ["/v2/settings"],
			}),
		});

		expect(router.buildLocation({ to: "/settings" }).href).toBe("/v2/settings");
		expect(router.buildLocation({ to: "/" }).href).toBe("/v2/");
	});

	it("preserves runtime proxy prefixes in built hrefs", () => {
		const rootRoute = createRootRoute();
		const settingsRoute = createRoute({
			getParentRoute: () => rootRoute,
			path: "/settings",
			component: () => null,
		});
		const routeTree = rootRoute.addChildren([settingsRoute]);
		const router = createRouter({
			routeTree,
			basepath: resolveRouterBasePath({
				appBasePath: "/prefect/v2/",
				pathname: "/proxy/prefect/v2/settings",
			}),
			history: createMemoryHistory({
				initialEntries: ["/proxy/prefect/v2/settings"],
			}),
		});

		expect(router.buildLocation({ to: "/settings" }).href).toBe(
			"/proxy/prefect/v2/settings",
		);
		expect(router.buildLocation({ to: "/" }).href).toBe("/proxy/prefect/v2/");
	});

	it("uses the final base-path occurrence when a proxy prefix contains the app base", () => {
		const rootRoute = createRootRoute();
		const settingsRoute = createRoute({
			getParentRoute: () => rootRoute,
			path: "/settings",
			component: () => null,
		});
		const routeTree = rootRoute.addChildren([settingsRoute]);
		const router = createRouter({
			routeTree,
			basepath: resolveRouterBasePath({
				appBasePath: "/v2/",
				pathname: "/company/v2/prefect/v2/settings",
			}),
			history: createMemoryHistory({
				initialEntries: ["/company/v2/prefect/v2/settings"],
			}),
		});

		expect(router.buildLocation({ to: "/settings" }).href).toBe(
			"/company/v2/prefect/v2/settings",
		);
		expect(router.buildLocation({ to: "/" }).href).toBe(
			"/company/v2/prefect/v2/",
		);
	});
});
