import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useCallback, useMemo, useState } from "react";
import {
	buildPaginateFlowRunsQuery,
	type FlowRunsFilter,
	type FlowRunsPaginateFilter,
} from "@/api/flow-runs";
import { FlowRunCard } from "@/components/flow-runs/flow-run-card";
import {
	Pagination,
	PaginationContent,
	PaginationItem,
	PaginationNextButton,
	PaginationPreviousButton,
} from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { Typography } from "@/components/ui/typography";

type FlowRunsAccordionContentProps = {
	/** The flow ID to display runs for */
	flowId: string;
	/** Filter for flow runs */
	filter?: FlowRunsFilter;
};

const ITEMS_PER_PAGE = 3;

/**
 * Content component for each accordion section.
 * Displays a paginated list of flow runs for a specific flow.
 */
export function FlowRunsAccordionContent({
	flowId,
	filter,
}: FlowRunsAccordionContentProps) {
	const [page, setPage] = useState(1);
	const queryClient = useQueryClient();

	// Build filter for this specific flow with pagination
	const buildFilterForPage = useCallback(
		(targetPage: number): FlowRunsPaginateFilter => {
			return {
				...filter,
				flows: {
					...filter?.flows,
					operator: "and_" as const,
					id: { any_: [flowId] },
				},
				page: targetPage,
				limit: ITEMS_PER_PAGE,
				sort: "START_TIME_DESC" as const,
			};
		},
		[filter, flowId],
	);

	const paginatedFilter = useMemo(
		() => buildFilterForPage(page),
		[buildFilterForPage, page],
	);

	// Fetch paginated flow runs
	const { data } = useQuery(
		buildPaginateFlowRunsQuery(paginatedFilter, 30_000),
	);

	const flowRuns = data?.results ?? [];
	const totalPages = data?.pages ?? 1;

	// Prefetch next page on hover
	const prefetchNextPage = useCallback(() => {
		if (page < totalPages) {
			const nextPageFilter = buildFilterForPage(page + 1);
			void queryClient.prefetchQuery(
				buildPaginateFlowRunsQuery(nextPageFilter, 30_000),
			);
		}
	}, [page, totalPages, buildFilterForPage, queryClient]);

	// Prefetch previous page on hover
	const prefetchPreviousPage = useCallback(() => {
		if (page > 1) {
			const prevPageFilter = buildFilterForPage(page - 1);
			void queryClient.prefetchQuery(
				buildPaginateFlowRunsQuery(prevPageFilter, 30_000),
			);
		}
	}, [page, buildFilterForPage, queryClient]);

	return (
		<div className="space-y-3">
			{flowRuns.map((flowRun) => (
				<Suspense key={flowRun.id} fallback={<FlowRunCardSkeleton />}>
					<FlowRunCard flowRun={flowRun} />
				</Suspense>
			))}

			{totalPages > 1 && (
				<Pagination className="justify-start">
					<PaginationContent>
						<PaginationItem>
							<PaginationPreviousButton
								onClick={() => setPage((p) => Math.max(1, p - 1))}
								onMouseEnter={prefetchPreviousPage}
								disabled={page === 1}
							/>
						</PaginationItem>
						<PaginationItem>
							<Typography variant="bodySmall" className="px-2">
								Page {page} of {totalPages}
							</Typography>
						</PaginationItem>
						<PaginationItem>
							<PaginationNextButton
								onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
								onMouseEnter={prefetchNextPage}
								disabled={page === totalPages}
							/>
						</PaginationItem>
					</PaginationContent>
				</Pagination>
			)}
		</div>
	);
}

function FlowRunCardSkeleton() {
	return (
		<div className="flex flex-col gap-2 rounded-md border p-4">
			<div className="flex justify-between items-center">
				<Skeleton className="h-4 w-32" />
				<Skeleton className="h-4 w-16" />
			</div>
			<div className="flex items-center gap-2">
				<Skeleton className="h-5 w-20" />
				<Skeleton className="h-4 w-24" />
				<Skeleton className="h-4 w-16" />
			</div>
		</div>
	);
}
