import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRouteWithContext,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { delay, HttpResponse, http } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import type { components } from "@/api/prefect";
import {
	createFakeGlobalConcurrencyLimit,
	createFakeTaskRunConcurrencyLimit,
} from "@/mocks";
import { Route } from "@/routes/concurrency-limits";

type PaginationBody =
	components["schemas"]["Body_paginate_concurrency_limits_v2_v2_concurrency_limits_paginate_post"] &
		components["schemas"]["Body_paginate_concurrency_limits_concurrency_limits_paginate_post"];

const renderPage = (tab: "global" | "task-run", page = 1) => {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	const root = createRootRouteWithContext<{ queryClient: QueryClient }>()();
	Object.assign(Route.options, {
		getParentRoute: () => root,
		path: "/concurrency-limits/",
	});
	const router = createRouter({
		routeTree: root.addChildren([Route]),
		history: createMemoryHistory({
			initialEntries: [`/concurrency-limits?tab=${tab}&page=${page}&limit=10`],
		}),
		context: { queryClient },
	});
	const view = render(<RouterProvider router={router} />, {
		wrapper: createWrapper({ queryClient }),
	});
	return { ...view, router };
};

const mockLimits = (tab: "global" | "task-run") => {
	const prefix =
		tab === "global" ? "/v2/concurrency_limits" : "/concurrency_limits";
	const limits = Array.from({ length: 250 }, (_, index) => {
		const name = `limit-${index.toString().padStart(3, "0")}`;
		return tab === "global"
			? createFakeGlobalConcurrencyLimit({ name })
			: createFakeTaskRunConcurrencyLimit({ tag: name, active_slots: [] });
	});
	let responseDelay = 0;
	server.use(
		http.post(buildApiUrl(`${prefix}/count`), () =>
			HttpResponse.json(limits.length),
		),
		http.post(buildApiUrl(`${prefix}/paginate`), async ({ request }) => {
			const {
				page = 1,
				limit = 10,
				concurrency_limits,
			} = (await request.json()) as PaginationBody;
			const search = (
				concurrency_limits?.name?.like_ ??
				concurrency_limits?.tag?.like_ ??
				""
			).toLowerCase();
			const filtered = limits.filter((row) =>
				("name" in row ? row.name : row.tag).toLowerCase().includes(search),
			);
			if (responseDelay) await delay(responseDelay);
			return HttpResponse.json({
				results: filtered.slice((page - 1) * limit, page * limit),
				count: filtered.length,
				pages: Math.ceil(filtered.length / limit),
				page,
				limit,
			});
		}),
	);
	return {
		delayResponses: () => {
			responseDelay = 200;
		},
	};
};

afterEach(() => localStorage.clear());

describe.each(["global", "task-run"] as const)(
	"%s concurrency limits page",
	(tab) => {
		it("paginates and searches across more than 200 limits using URL state", async () => {
			mockLimits(tab);
			let hiddenPageRequests = 0;
			let hiddenCountRequests = 0;
			const hiddenPrefix =
				tab === "global" ? "/concurrency_limits" : "/v2/concurrency_limits";
			server.use(
				http.post(buildApiUrl(`${hiddenPrefix}/paginate`), () => {
					hiddenPageRequests += 1;
					return HttpResponse.json({
						results: [],
						count: 0,
						pages: 0,
						page: 1,
						limit: 10,
					});
				}),
				http.post(buildApiUrl(`${hiddenPrefix}/count`), () => {
					hiddenCountRequests += 1;
					return HttpResponse.json(0);
				}),
			);
			const user = userEvent.setup();
			const { router } = renderPage(tab, 22);

			expect(await screen.findByText("limit-210")).toBeVisible();
			expect(screen.getByText(/page 22 of 25/i)).toBeVisible();
			await user.click(
				screen.getByRole("button", { name: /go to last page/i }),
			);
			expect(await screen.findByText("limit-249")).toBeVisible();
			expect(router.state.location.search).toMatchObject({
				page: 25,
				limit: 10,
			});

			await user.type(
				screen.getByPlaceholderText(/search .*limit/i),
				"limit-249",
			);
			await waitFor(() =>
				expect(screen.getByText(/page 1 of 1/i)).toBeVisible(),
			);
			expect(router.state.location.search).toMatchObject({
				search: "limit-249",
				page: 1,
			});
			expect(screen.getByText("limit-249")).toBeVisible();
			expect(screen.queryByText("limit-240")).not.toBeInTheDocument();
			expect(hiddenPageRequests).toBe(0);
			expect(hiddenCountRequests).toBe(0);

			const nextTab = tab === "global" ? "task-run" : "global";
			await user.click(
				screen.getByRole("tab", {
					name: nextTab === "global" ? "Global" : "Task Run",
				}),
			);
			await waitFor(() => expect(hiddenPageRequests).toBeGreaterThan(0));
			await waitFor(() => expect(hiddenCountRequests).toBeGreaterThan(0));
			expect(router.state.location.search).toMatchObject({ tab: nextTab });
		});

		it("keeps previous rows and the search input mounted while loading a new page", async () => {
			const mock = mockLimits(tab);
			const user = userEvent.setup();
			renderPage(tab);
			expect(await screen.findByText("limit-000")).toBeVisible();
			const input = screen.getByPlaceholderText(/search .*limit/i);
			mock.delayResponses();

			await user.click(
				screen.getByRole("button", { name: /go to next page/i }),
			);
			expect(screen.getByText("limit-000")).toBeVisible();
			expect(screen.getByPlaceholderText(/search .*limit/i)).toBe(input);
			expect(await screen.findByText("limit-010")).toBeVisible();
		});
	},
);
