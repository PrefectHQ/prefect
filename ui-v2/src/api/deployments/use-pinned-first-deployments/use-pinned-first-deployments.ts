import { type QueryClient, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
	buildCountDeploymentsQuery,
	buildFilterDeploymentsQuery,
	type DeploymentsFilter,
} from "@/api/deployments";
import type { components } from "@/api/prefect";

type DeploymentsListOptions = {
	sort: components["schemas"]["DeploymentSort"];
	deployments: Omit<components["schemas"]["DeploymentFilter"], "id">;
};

type PageOptions = {
	page: number;
	limit: number;
};

/**
 * Splits one page of a "pinned deployments first" list into the part covered
 * by pinned deployments and the part covered by everything else.
 *
 * @example
 * ```ts
 * // 3 pinned deployments, 10 per page
 * getPinnedFirstWindow({ page: 1, limit: 10, pinnedCount: 3 });
 * // { pinnedStart: 0, pinnedEnd: 3, unpinnedOffset: 0, unpinnedLimit: 7 }
 * getPinnedFirstWindow({ page: 2, limit: 10, pinnedCount: 3 });
 * // { pinnedStart: 3, pinnedEnd: 3, unpinnedOffset: 7, unpinnedLimit: 10 }
 * ```
 */
export const getPinnedFirstWindow = ({
	page,
	limit,
	pinnedCount,
}: PageOptions & { pinnedCount: number }) => {
	const start = (page - 1) * limit;
	const pinnedStart = Math.min(start, pinnedCount);
	const pinnedEnd = Math.min(start + limit, pinnedCount);
	return {
		pinnedStart,
		pinnedEnd,
		unpinnedOffset: start - pinnedStart,
		unpinnedLimit: limit - (pinnedEnd - pinnedStart),
	};
};

/**
 * Query for the pinned deployments matching the current filters, in sort
 * order. No limit is sent because the server rejects limits above its
 * configured default; if there are more pins than that, the server truncates
 * the list and the remaining pins sort with the unpinned deployments.
 */
const buildPinnedDeploymentsQuery = ({
	sort,
	deployments,
	pinnedDeploymentIds,
}: DeploymentsListOptions & { pinnedDeploymentIds: readonly string[] }) =>
	buildFilterDeploymentsQuery(
		{
			offset: 0,
			sort,
			deployments: { ...deployments, id: { any_: [...pinnedDeploymentIds] } },
		},
		{ enabled: pinnedDeploymentIds.length > 0 },
	);

const buildUnpinnedFilter = ({
	sort,
	deployments,
	excludedDeploymentIds,
}: DeploymentsListOptions & {
	excludedDeploymentIds: string[];
}): DeploymentsFilter => ({
	offset: 0,
	sort,
	deployments: {
		...deployments,
		...(excludedDeploymentIds.length > 0
			? { id: { not_any_: excludedDeploymentIds } }
			: {}),
	},
});

const buildUnpinnedDeploymentsCountQuery = (
	options: DeploymentsListOptions & { excludedDeploymentIds: string[] },
) => buildCountDeploymentsQuery(buildUnpinnedFilter(options));

const buildUnpinnedDeploymentsQuery = (
	options: DeploymentsListOptions &
		PageOptions & { excludedDeploymentIds: string[] },
	{ enabled = true }: { enabled?: boolean } = {},
) => {
	const { unpinnedOffset, unpinnedLimit } = getPinnedFirstWindow({
		...options,
		pinnedCount: options.excludedDeploymentIds.length,
	});
	return buildFilterDeploymentsQuery(
		{
			...buildUnpinnedFilter(options),
			offset: unpinnedOffset,
			limit: unpinnedLimit,
		},
		{ enabled: enabled && unpinnedLimit > 0 },
	);
};

type PinnedFirstOptions = DeploymentsListOptions &
	PageOptions & { pinnedDeploymentIds: readonly string[] };

/**
 * Warms the cache for `usePinnedFirstDeployments` from a route loader and
 * resolves to the deployments on the page, so the loader can prefetch what
 * depends on them.
 */
export const prefetchPinnedFirstDeployments = async (
	queryClient: QueryClient,
	options: PinnedFirstOptions,
) => {
	const pinned =
		options.pinnedDeploymentIds.length > 0
			? await queryClient.ensureQueryData(buildPinnedDeploymentsQuery(options))
			: [];
	const unpinnedOptions = {
		...options,
		excludedDeploymentIds: pinned.map((deployment) => deployment.id),
	};
	const { pinnedStart, pinnedEnd, unpinnedLimit } = getPinnedFirstWindow({
		...options,
		pinnedCount: pinned.length,
	});
	void queryClient.prefetchQuery(
		buildUnpinnedDeploymentsCountQuery(unpinnedOptions),
	);
	const unpinned =
		unpinnedLimit > 0
			? await queryClient.ensureQueryData(
					buildUnpinnedDeploymentsQuery(unpinnedOptions),
				)
			: [];
	return [...pinned.slice(pinnedStart, pinnedEnd), ...unpinned];
};

/**
 * Fetches one page of deployments with this browser's pinned deployments
 * sorted ahead of the rest, across pages: pinned deployments fill the first
 * page(s), and the remaining deployments follow in the requested sort order.
 */
export function usePinnedFirstDeployments(options: PinnedFirstOptions) {
	const hasPins = options.pinnedDeploymentIds.length > 0;

	const pinnedQuery = useQuery(buildPinnedDeploymentsQuery(options));
	const pinned = hasPins ? (pinnedQuery.data ?? []) : [];
	const isPinnedReady = !hasPins || pinnedQuery.data !== undefined;
	const excludedDeploymentIds = pinned.map((deployment) => deployment.id);

	const pageWindow = getPinnedFirstWindow({
		...options,
		pinnedCount: pinned.length,
	});
	const needsUnpinned = pageWindow.unpinnedLimit > 0;

	const unpinnedQuery = useQuery(
		buildUnpinnedDeploymentsQuery(
			{ ...options, excludedDeploymentIds },
			{ enabled: isPinnedReady },
		),
	);
	const unpinnedCountQuery = useQuery({
		...buildUnpinnedDeploymentsCountQuery({
			...options,
			excludedDeploymentIds,
		}),
		enabled: isPinnedReady,
	});

	const queries = [
		...(hasPins ? [pinnedQuery] : []),
		...(needsUnpinned ? [unpinnedQuery] : []),
		unpinnedCountQuery,
	];
	const failedQuery = queries.find((query) => query.isError);
	const isPending = queries.some((query) => query.isPending);
	const isPlaceholderData = queries.some((query) => query.isPlaceholderData);

	const pinnedData = pinnedQuery.data;
	const unpinnedData = unpinnedQuery.data;
	const unpinnedCount = unpinnedCountQuery.data;
	const { pinnedStart, pinnedEnd } = pageWindow;
	const current = useMemo(() => {
		const pinnedOnPage = hasPins ? (pinnedData ?? []) : [];
		return {
			deployments: [
				...pinnedOnPage.slice(pinnedStart, pinnedEnd),
				...(needsUnpinned ? (unpinnedData ?? []) : []),
			],
			count: pinnedOnPage.length + (unpinnedCount ?? 0),
		};
	}, [
		hasPins,
		needsUnpinned,
		pinnedData,
		unpinnedData,
		unpinnedCount,
		pinnedStart,
		pinnedEnd,
	]);

	// The queries resolve at different times. Mixing a fresh pinned list with a
	// stale unpinned one shows a deployment twice or not at all for a moment,
	// so keep the last list whose parts agree until the next one is complete.
	const isConsistent = !isPending && !isPlaceholderData;
	const [consistent, setConsistent] = useState(current);
	if (isConsistent && consistent !== current) {
		setConsistent(current);
	}
	const { deployments, count } = isConsistent ? current : consistent;

	return {
		deployments,
		count,
		pages: Math.ceil(count / options.limit),
		isPending,
		isPlaceholderData,
		isError: failedQuery !== undefined,
		error: failedQuery?.error ?? null,
		refetch: () => Promise.all(queries.map((query) => query.refetch())),
	};
}
