import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { Suspense } from "react";
import { z } from "zod";
import { buildEventsHistoryQuery, buildFilterEventsQuery } from "@/api/events";
import {
	buildEventsCountFilterFromSearch,
	buildEventsFilterFromSearch,
	type EventsSearchParams,
} from "@/api/events/filters";
import { EventsPage } from "@/components/events/events-page";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Schema for validating URL search parameters for the events page.
 * Uses existing parameter names (resource, event) for compatibility with API infrastructure.
 */
const searchParams = z.object({
	resource: z.array(z.string()).optional(),
	event: z.array(z.string()).optional(),
	rangeType: z.enum(["span", "range"]).optional().default("span"),
	seconds: z.number().optional().default(-86400),
	start: z.string().optional(),
	end: z.string().optional(),
	order: z.enum(["ASC", "DESC"]).optional(),
});

/**
 * Skeleton component shown while the events page is loading.
 * Displays placeholder elements for header, filters, chart, and timeline.
 */
function EventsPageSkeleton() {
	return (
		<div className="flex flex-col gap-4">
			{/* Header skeleton */}
			<Skeleton className="h-8 w-48" />
			{/* Filters skeleton */}
			<div className="flex flex-wrap gap-4">
				<Skeleton className="h-10 w-48" />
				<Skeleton className="h-10 w-48" />
				<Skeleton className="h-10 w-48" />
			</div>
			{/* Chart area skeleton */}
			<Skeleton className="h-32 w-full" />
			{/* Timeline area skeleton */}
			<Skeleton className="h-64 w-full" />
		</div>
	);
}

export const Route = createFileRoute("/events/")({
	validateSearch: zodValidator(searchParams),
	loaderDeps: ({ search }) => search,
	wrapInSuspense: true,
	pendingComponent: EventsPageSkeleton,
	loader: ({ deps: search, context: { queryClient } }) => {
		const eventsFilter = buildEventsFilterFromSearch(search);
		const countFilter = buildEventsCountFilterFromSearch(search);

		// Prefetch queries without blocking route loading
		void queryClient.prefetchQuery(buildFilterEventsQuery(eventsFilter));
		void queryClient.prefetchQuery(buildEventsHistoryQuery(countFilter));
	},
	component: RouteComponent,
});

function RouteComponent() {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const handleSearchChange = (updates: Partial<EventsSearchParams>) => {
		void navigate({
			to: ".",
			search: (prev) => ({ ...prev, ...updates }),
			replace: true,
		});
	};

	return (
		<Suspense fallback={<EventsPageSkeleton />}>
			<EventsPage search={search} onSearchChange={handleSearchChange} />
		</Suspense>
	);
}
