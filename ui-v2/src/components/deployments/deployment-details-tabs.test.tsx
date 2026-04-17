import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { createFakeDeployment } from "@/mocks";
import { DeploymentDetailsTabs } from "./deployment-details-tabs";

const searchParams = z.object({
	tab: z
		.enum([
			"Details",
			"Runs",
			"Upcoming",
			"Parameters",
			"Configuration",
			"Description",
		])
		.default("Details"),
});

type MatchMediaMock = ReturnType<typeof createMatchMediaMock>;

function createMatchMediaMock(isDesktop: boolean) {
	const listeners = new Set<(event: MediaQueryListEvent) => void>();
	const mql = {
		matches: isDesktop,
		media: "(min-width: 1024px)",
		onchange: null,
		addEventListener: vi.fn(
			(_event: "change", listener: (event: MediaQueryListEvent) => void) => {
				listeners.add(listener);
			},
		),
		removeEventListener: vi.fn(
			(_event: "change", listener: (event: MediaQueryListEvent) => void) => {
				listeners.delete(listener);
			},
		),
		dispatchEvent: vi.fn(),
		// Legacy API for completeness
		addListener: vi.fn(),
		removeListener: vi.fn(),
	};
	return {
		mql,
		emitChange(matches: boolean) {
			mql.matches = matches;
			const event = { matches, media: mql.media } as MediaQueryListEvent;
			for (const listener of listeners) {
				listener(event);
			}
		},
	};
}

const renderDeploymentDetailsTabs = ({
	initialTab,
	detailsContent,
}: {
	initialTab?: "Details" | "Runs" | "Upcoming";
	detailsContent?: React.ReactNode;
} = {}) => {
	const deployment = createFakeDeployment({ name: "test-deployment" });

	const rootRoute = createRootRoute();
	const deploymentRoute = createRoute({
		path: "/deployments/deployment/$id",
		getParentRoute: () => rootRoute,
		validateSearch: zodValidator(searchParams),
		component: () => (
			<DeploymentDetailsTabs
				deployment={deployment}
				detailsContent={detailsContent ?? <div>sidebar details</div>}
			/>
		),
	});

	const routeTree = rootRoute.addChildren([deploymentRoute]);
	const initialSearch = initialTab ? `?tab=${initialTab}` : "";
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({
			initialEntries: [`/deployments/deployment/test-id${initialSearch}`],
		}),
		context: { queryClient: new QueryClient() },
	});

	return {
		...render(<RouterProvider router={router} />, {
			wrapper: createWrapper(),
		}),
		router,
	};
};

describe("DeploymentDetailsTabs", () => {
	const originalMatchMedia = window.matchMedia;
	let matchMediaMock: MatchMediaMock;

	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => HttpResponse.json([])),
			http.post(buildApiUrl("/flow_runs/count"), () => HttpResponse.json(0)),
		);
		// JSDOM does not resolve Tailwind theme vars, so stub `--breakpoint-lg`
		// on the CSSStyleDeclaration prototype to match Tailwind's default
		// (`64rem`). This keeps the component's `matchMedia` query in sync
		// with the `lg:hidden` CSS class it coordinates with.
		vi.spyOn(
			CSSStyleDeclaration.prototype,
			"getPropertyValue",
		).mockImplementation((name: string) =>
			name === "--breakpoint-lg" ? "64rem" : "",
		);
	});

	afterEach(() => {
		Object.defineProperty(window, "matchMedia", {
			writable: true,
			configurable: true,
			value: originalMatchMedia,
		});
		vi.restoreAllMocks();
	});

	const mockMatchMedia = (isDesktop: boolean) => {
		matchMediaMock = createMatchMediaMock(isDesktop);
		Object.defineProperty(window, "matchMedia", {
			writable: true,
			configurable: true,
			value: vi.fn().mockReturnValue(matchMediaMock.mql),
		});
	};

	it("keeps the Details tab selected on narrow viewports", async () => {
		mockMatchMedia(false);
		const { router } = renderDeploymentDetailsTabs();

		await waitFor(() => {
			expect(screen.getByText("sidebar details")).toBeInTheDocument();
		});

		expect(router.state.location.search).toEqual({ tab: "Details" });
	});

	it("redirects Details to Runs on wide viewports", async () => {
		mockMatchMedia(true);
		const { router } = renderDeploymentDetailsTabs();

		await waitFor(() => {
			expect(router.state.location.search).toEqual({ tab: "Runs" });
		});
	});

	it("redirects Details to Runs when the viewport crosses the lg breakpoint", async () => {
		mockMatchMedia(false);
		const { router } = renderDeploymentDetailsTabs();

		await waitFor(() => {
			expect(router.state.location.search).toEqual({ tab: "Details" });
		});

		matchMediaMock.emitChange(true);

		await waitFor(() => {
			expect(router.state.location.search).toEqual({ tab: "Runs" });
		});
	});

	it("leaves non-Details tabs alone on wide viewports", async () => {
		mockMatchMedia(true);
		const { router } = renderDeploymentDetailsTabs({ initialTab: "Upcoming" });

		await waitFor(() => {
			expect(router.state.location.search).toEqual({ tab: "Upcoming" });
		});
	});
});
