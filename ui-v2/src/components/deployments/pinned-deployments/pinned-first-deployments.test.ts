import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { DeploymentsFilter } from "@/api/deployments";
import { createFakeDeployment } from "@/mocks";
import {
	getPinnedFirstWindow,
	usePinnedFirstDeployments,
} from "./pinned-first-deployments";

const NAMES = ["a", "b", "c", "d", "e", "f", "g"];
const DEPLOYMENTS = NAMES.map((name) =>
	createFakeDeployment({ id: `id-${name}`, name }),
);

const LIST_OPTIONS = {
	sort: "NAME_ASC",
	deployments: { operator: "and_" },
} as const;

/**
 * Serves DEPLOYMENTS (already in NAME_ASC order) the way the API does for the
 * id filters, offset, and limit. `maxResults` stands in for the server's
 * configured default limit.
 */
const mockDeploymentsApi = ({ maxResults = 200 } = {}) => {
	const match = (body: DeploymentsFilter) => {
		const id = body.deployments?.id;
		return DEPLOYMENTS.filter(
			(deployment) =>
				(!id?.any_ || id.any_.includes(deployment.id)) &&
				!id?.not_any_?.includes(deployment.id),
		);
	};
	server.use(
		http.post(buildApiUrl("/deployments/filter"), async ({ request }) => {
			const body = (await request.json()) as DeploymentsFilter;
			const offset = body.offset ?? 0;
			const limit = Math.min(body.limit ?? maxResults, maxResults);
			return HttpResponse.json(match(body).slice(offset, offset + limit));
		}),
		http.post(buildApiUrl("/deployments/count"), async ({ request }) => {
			const body = (await request.json()) as DeploymentsFilter;
			return HttpResponse.json(match(body).length);
		}),
	);
};

const renderPinnedFirst = (options: {
	page: number;
	limit: number;
	pinnedDeploymentIds: string[];
}) =>
	renderHook(() => usePinnedFirstDeployments({ ...LIST_OPTIONS, ...options }), {
		wrapper: createWrapper(),
	});

const names = (deployments: { name: string }[]) =>
	deployments.map((deployment) => deployment.name);

describe("getPinnedFirstWindow", () => {
	it.each([
		{
			title: "no pins",
			input: { page: 2, limit: 10, pinnedCount: 0 },
			expected: {
				pinnedStart: 0,
				pinnedEnd: 0,
				unpinnedOffset: 10,
				unpinnedLimit: 10,
			},
		},
		{
			title: "pins share the first page",
			input: { page: 1, limit: 10, pinnedCount: 3 },
			expected: {
				pinnedStart: 0,
				pinnedEnd: 3,
				unpinnedOffset: 0,
				unpinnedLimit: 7,
			},
		},
		{
			title: "later pages continue where the first page stopped",
			input: { page: 2, limit: 10, pinnedCount: 3 },
			expected: {
				pinnedStart: 3,
				pinnedEnd: 3,
				unpinnedOffset: 7,
				unpinnedLimit: 10,
			},
		},
		{
			title: "pins fill a whole page",
			input: { page: 1, limit: 5, pinnedCount: 12 },
			expected: {
				pinnedStart: 0,
				pinnedEnd: 5,
				unpinnedOffset: 0,
				unpinnedLimit: 0,
			},
		},
		{
			title: "pins end partway through a later page",
			input: { page: 3, limit: 5, pinnedCount: 12 },
			expected: {
				pinnedStart: 10,
				pinnedEnd: 12,
				unpinnedOffset: 0,
				unpinnedLimit: 3,
			},
		},
	])("$title", ({ input, expected }) => {
		expect(getPinnedFirstWindow(input)).toEqual(expected);
	});
});

describe("usePinnedFirstDeployments", () => {
	beforeEach(() => {
		mockDeploymentsApi();
	});

	it("lists deployments in sort order when nothing is pinned", async () => {
		const { result } = renderPinnedFirst({
			page: 1,
			limit: 3,
			pinnedDeploymentIds: [],
		});

		await waitFor(() => expect(result.current.isPending).toBe(false));
		expect(names(result.current.deployments)).toEqual(["a", "b", "c"]);
		expect(result.current.count).toBe(7);
		expect(result.current.pages).toBe(3);
	});

	it("lists pinned deployments first", async () => {
		const { result } = renderPinnedFirst({
			page: 1,
			limit: 3,
			pinnedDeploymentIds: ["id-f", "id-d"],
		});

		await waitFor(() => expect(result.current.isPending).toBe(false));
		expect(names(result.current.deployments)).toEqual(["d", "f", "a"]);
		expect(result.current.count).toBe(7);
		expect(result.current.pages).toBe(3);
	});

	it("continues later pages without repeating or skipping deployments", async () => {
		const pinnedDeploymentIds = ["id-f", "id-d"];
		const seen: string[] = [];
		for (const page of [1, 2, 3]) {
			const { result, unmount } = renderPinnedFirst({
				page,
				limit: 3,
				pinnedDeploymentIds,
			});
			await waitFor(() => expect(result.current.isPending).toBe(false));
			seen.push(...names(result.current.deployments));
			unmount();
		}

		expect(seen).toEqual(["d", "f", "a", "b", "c", "e", "g"]);
	});

	it("spreads pins over several pages when they outnumber the page size", async () => {
		const pinnedDeploymentIds = ["id-g", "id-e", "id-c"];
		const first = renderPinnedFirst({ page: 1, limit: 2, pinnedDeploymentIds });
		await waitFor(() => expect(first.result.current.isPending).toBe(false));
		expect(names(first.result.current.deployments)).toEqual(["c", "e"]);

		const second = renderPinnedFirst({
			page: 2,
			limit: 2,
			pinnedDeploymentIds,
		});
		await waitFor(() => expect(second.result.current.isPending).toBe(false));
		expect(names(second.result.current.deployments)).toEqual(["g", "a"]);
	});

	it("ignores pins for deployments that no longer exist", async () => {
		const { result } = renderPinnedFirst({
			page: 1,
			limit: 3,
			pinnedDeploymentIds: ["id-deleted", "id-c"],
		});

		await waitFor(() => expect(result.current.isPending).toBe(false));
		expect(names(result.current.deployments)).toEqual(["c", "a", "b"]);
		expect(result.current.count).toBe(7);
	});

	it("keeps pins the server truncated in the rest of the list", async () => {
		mockDeploymentsApi({ maxResults: 2 });
		const pinnedDeploymentIds = ["id-g", "id-e", "id-c"];
		const seen: string[] = [];
		for (const page of [1, 2, 3, 4]) {
			const { result, unmount } = renderPinnedFirst({
				page,
				limit: 2,
				pinnedDeploymentIds,
			});
			await waitFor(() => expect(result.current.isPending).toBe(false));
			seen.push(...names(result.current.deployments));
			unmount();
		}

		expect(seen).toEqual(["c", "e", "a", "b", "d", "f", "g"]);
	});
});
