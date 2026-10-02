import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import type { PaginationState } from "@tanstack/react-table";
import { useCallback, useMemo } from "react";
import { z } from "zod";
import { categorizeError } from "@/api/error-utils";
import {
	buildCountGlobalConcurrencyLimitsQuery,
	buildGlobalConcurrencyLimitsPaginationBody,
	buildPaginateGlobalConcurrencyLimitsQuery,
} from "@/api/global-concurrency-limits";
import {
	buildCountTaskRunConcurrencyLimitsQuery,
	buildPaginateTaskRunConcurrencyLimitsQuery,
	buildTaskRunConcurrencyLimitsPaginationBody,
} from "@/api/task-run-concurrency-limits";
import { ConcurrencyLimitsPage } from "@/components/concurrency/concurrency-limits-page";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";
import { usePageSizePreference } from "@/hooks/use-page-size-preference";
import { usePageTitle } from "@/hooks/use-page-title";

/**
 * Schema for validating URL search parameters for the Concurrency Limits page.
 * @property {string} search used to filter data table
 * @property {'global' | 'task-run'} tab used designate which tab view to display
 * @property {number} page page of concurrency limits to display. Must be positive. Defaults to 1.
 * @property {number} limit number of concurrency limits to display per page. Must be positive.
 */
const searchParams = z.object({
	search: z.string().optional(),
	tab: z.enum(["global", "task-run"]).default("global"),
	page: z.number().int().positive().optional().default(1).catch(1),
	limit: z.number().int().positive().max(200).optional().catch(undefined),
});

export type TabOptions = z.infer<typeof searchParams>["tab"];

export const Route = createFileRoute("/concurrency-limits/")({
	validateSearch: searchParams,
	component: RouteComponent,
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
	loaderDeps: ({ search }) => ({
		tab: search.tab,
		page: search.page,
		limit: search.limit,
		search: search.search,
	}),
	loader: ({ deps, context }) => {
		// Prefetch the page of concurrency limits and their counts without blocking
		// the loader, so the search input stays interactive while results update.
		if (deps.tab === "global") {
			void context.queryClient.prefetchQuery(
				buildPaginateGlobalConcurrencyLimitsQuery(
					buildGlobalConcurrencyLimitsPaginationBody(deps),
				),
			);
		} else {
			void context.queryClient.prefetchQuery(
				buildPaginateTaskRunConcurrencyLimitsQuery(
					buildTaskRunConcurrencyLimitsPaginationBody(deps),
				),
			);
		}
		void context.queryClient.prefetchQuery(
			buildCountGlobalConcurrencyLimitsQuery(),
		);
		void context.queryClient.prefetchQuery(
			buildCountTaskRunConcurrencyLimitsQuery(),
		);
	},
	errorComponent: function ConcurrencyLimitsErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(
			error,
			"Failed to load concurrency limits",
		);
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Concurrency Limits</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
});

/**
 * Holds the search and pagination state of both concurrency limit tables in the
 * URL. React Table uses 0-based page indexes, the URL uses 1-based page numbers.
 */
function RouteComponent() {
	usePageTitle("Concurrency Limits");
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onInitializePageSize = useCallback(
		(pageSize: number) => {
			void navigate({
				to: ".",
				search: (prev) => ({ ...prev, limit: pageSize }),
				replace: true,
			});
		},
		[navigate],
	);

	const pageSize = usePageSizePreference(search.limit, onInitializePageSize);

	const pagination: PaginationState = useMemo(
		() => ({ pageIndex: search.page - 1, pageSize }),
		[search.page, pageSize],
	);

	const onPaginationChange = useCallback(
		(newPagination: PaginationState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					page: newPagination.pageIndex + 1,
					limit: newPagination.pageSize,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	// A new search value changes the number of results, so go back to page one.
	const onSearchChange = useCallback(
		(value: string) => {
			void navigate({
				to: ".",
				search: (prev) => ({ ...prev, search: value, page: 1 }),
				replace: true,
			});
		},
		[navigate],
	);

	return (
		<ConcurrencyLimitsPage
			search={search.search}
			onSearchChange={onSearchChange}
			pagination={pagination}
			onPaginationChange={onPaginationChange}
		/>
	);
}
