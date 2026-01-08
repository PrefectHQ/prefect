import { useQuery } from "@tanstack/react-query";
import { Suspense, useEffect, useState } from "react";
import { buildEventsHistoryQuery } from "@/api/events";
import {
	buildEventsCountFilterFromSearch,
	buildEventsFilterFromSearch,
	type EventsSearchParams,
	getDateRangeFromSearch,
} from "@/api/events/filters";
import { Card, CardContent } from "@/components/ui/card";
import {
	type DateRangeSelectValue,
	RichDateRangeSelector,
} from "@/components/ui/date-range-select";
import {
	EmptyState,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import {
	Pagination,
	PaginationContent,
	PaginationItem,
	PaginationNextButton,
	PaginationPreviousButton,
} from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { Typography } from "@/components/ui/typography";
import { cn } from "@/utils";
import { InteractiveEventsChart } from "../events-line-chart";
import { EventsResourceFilter } from "../events-resource-filter";
import { EventsTimeline } from "../events-timeline";
import { EventsTypeFilter } from "../events-type-filter";
import { useEventsPagination } from "./use-events-pagination";

export type EventsPageProps = {
	search: EventsSearchParams;
	onSearchChange: (search: Partial<EventsSearchParams>) => void;
};

export function EventsPage({ search, onSearchChange }: EventsPageProps) {
	// Get the date range using the same logic as the route loader
	// This ensures query keys match and prevents infinite Suspense retries
	const dateRange = getDateRangeFromSearch(search);

	const eventsFilter = buildEventsFilterFromSearch(search);
	const countFilter = buildEventsCountFilterFromSearch({
		...search,
		rangeType: "range",
		start: dateRange.from,
		end: dateRange.to,
	});

	// Create separate filter for type dropdown (without event filter)
	// This ensures all event types are shown regardless of current selection
	const countFilterForTypeDropdown = buildEventsCountFilterFromSearch({
		resource: search.resource,
		rangeType: "range",
		start: dateRange.from,
		end: dateRange.to,
	});

	// Pagination
	const {
		events,
		currentPage,
		totalPages,
		isLoadingNextPage,
		goToNextPage,
		goToPreviousPage,
	} = useEventsPagination({ filter: eventsFilter });

	// Chart histogram data
	const { data: historyData } = useQuery(buildEventsHistoryQuery(countFilter));

	// Handlers - using correct property names that match EventsSearchParams
	const handleResourceIdsChange = (resourceIds: string[]) => {
		onSearchChange({ resource: resourceIds });
	};

	const handleEventTypesChange = (eventPrefixes: string[]) => {
		onSearchChange({ event: eventPrefixes });
	};

	const handleDateRangeChange = (value: DateRangeSelectValue) => {
		if (value?.type === "span") {
			onSearchChange({ rangeType: "span", seconds: value.seconds });
		} else if (value?.type === "range") {
			onSearchChange({
				rangeType: "range",
				start: value.startDate.toISOString(),
				end: value.endDate.toISOString(),
			});
		}
	};

	// Sticky chart behavior
	const [isChartSticky, setIsChartSticky] = useState(false);

	useEffect(() => {
		const handleScroll = () => {
			// Chart becomes sticky when scrolled past 100px
			setIsChartSticky(window.scrollY > 100);
		};

		window.addEventListener("scroll", handleScroll);
		return () => window.removeEventListener("scroll", handleScroll);
	}, []);

	return (
		<div className="flex flex-col gap-4">
			<div className="flex items-center justify-between">
				<h1 className="text-2xl font-semibold">Event Feed</h1>
			</div>

			{/* Filters */}
			<div className="grid grid-cols-1 gap-4 sm:grid-cols-[2fr_1fr]">
				<div className="flex flex-col gap-1">
					<Label>Resource</Label>
					<Suspense fallback={<Skeleton className="h-10 w-full" />}>
						<EventsResourceFilter
							selectedResourceIds={search.resource ?? []}
							onResourceIdsChange={handleResourceIdsChange}
						/>
					</Suspense>
				</div>
				<div className="flex flex-col gap-1">
					<Label>Events</Label>
					<Suspense fallback={<Skeleton className="h-10 w-full" />}>
						<EventsTypeFilter
							filter={countFilterForTypeDropdown}
							selectedEventTypes={search.event ?? []}
							onEventTypesChange={handleEventTypesChange}
						/>
					</Suspense>
				</div>
			</div>

			{/* Chart - sticky when scrolling */}
			<Card
				className={cn(
					"sticky top-0 z-10 transition-shadow",
					isChartSticky && "shadow-lg",
				)}
			>
				<CardContent className="pt-6">
					<InteractiveEventsChart
						data={historyData ?? []}
						className="h-32"
						startDate={new Date(dateRange.from)}
						endDate={new Date(dateRange.to)}
					/>
					<div className="flex justify-center pt-3">
						<RichDateRangeSelector
							value={
								search.rangeType === "range" && search.start && search.end
									? {
											type: "range",
											startDate: new Date(search.start),
											endDate: new Date(search.end),
										}
									: { type: "span", seconds: search.seconds ?? -86400 }
							}
							onValueChange={handleDateRangeChange}
						/>
					</div>
				</CardContent>
			</Card>

			{/* Events timeline or empty state */}
			{events.length === 0 ? (
				<EmptyState>
					<EmptyStateIcon id="Calendar" />
					<EmptyStateTitle>No events found</EmptyStateTitle>
					<EmptyStateDescription>
						No events match your current filters. Try adjusting your date range
						or filters.
					</EmptyStateDescription>
				</EmptyState>
			) : (
				<>
					<EventsTimeline events={events} />

					{/* Pagination */}
					{totalPages > 1 && (
						<div className="flex items-center justify-center gap-2">
							<Pagination>
								<PaginationContent>
									<PaginationItem>
										<PaginationPreviousButton
											onClick={goToPreviousPage}
											disabled={currentPage <= 1}
										/>
									</PaginationItem>
									<PaginationItem>
										<Typography variant="bodySmall" className="px-2">
											Page {currentPage} of {totalPages}
										</Typography>
									</PaginationItem>
									<PaginationItem>
										<PaginationNextButton
											onClick={goToNextPage}
											disabled={currentPage >= totalPages}
										/>
									</PaginationItem>
								</PaginationContent>
							</Pagination>
						</div>
					)}

					{isLoadingNextPage && (
						<div className="flex justify-center py-4">
							<Skeleton className="h-8 w-32" />
						</div>
					)}
				</>
			)}
		</div>
	);
}
