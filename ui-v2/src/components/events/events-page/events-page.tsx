import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense, useCallback, useEffect, useState } from "react";
import { buildEventsHistoryQuery } from "@/api/events";
import {
	buildEventsCountFilterFromSearch,
	buildEventsFilterFromSearch,
	type EventsSearchParams,
	getDateRangeFromSearch,
} from "@/api/events/filters";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
	// Get the initial date range using the same logic as the route loader
	// This ensures query keys match and prevents infinite Suspense retries
	const initialDateRange = getDateRangeFromSearch(search);

	// Chart zoom state (separate from filter date range)
	const [zoomStart, setZoomStart] = useState<Date>(
		() => new Date(initialDateRange.from),
	);
	const [zoomEnd, setZoomEnd] = useState<Date>(
		() => new Date(initialDateRange.to),
	);

	// Chart selection state (overrides zoom for filtering)
	const [selectionStart, setSelectionStart] = useState<Date | null>(null);
	const [selectionEnd, setSelectionEnd] = useState<Date | null>(null);

	// Build filters - use selection if present, otherwise use zoom/search dates
	const effectiveSearch: EventsSearchParams = {
		...search,
		...(selectionStart && selectionEnd
			? {
					rangeType: "range" as const,
					start: selectionStart.toISOString(),
					end: selectionEnd.toISOString(),
				}
			: {}),
	};

	const eventsFilter = buildEventsFilterFromSearch(effectiveSearch);
	const countFilter = buildEventsCountFilterFromSearch({
		...search,
		rangeType: "range",
		start: zoomStart.toISOString(),
		end: zoomEnd.toISOString(),
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
	const { data: historyData } = useSuspenseQuery(
		buildEventsHistoryQuery(countFilter),
	);

	// Handlers - using correct property names that match EventsSearchParams
	const handleResourceIdsChange = (resourceIds: string[]) => {
		onSearchChange({ resource: resourceIds });
	};

	const handleEventTypesChange = (eventPrefixes: string[]) => {
		onSearchChange({ event: eventPrefixes });
	};

	const handleDateRangeChange = (value: DateRangeSelectValue) => {
		// Clear selection when date range changes
		setSelectionStart(null);
		setSelectionEnd(null);

		if (value?.type === "span") {
			const newEnd = new Date();
			const newStart = new Date(newEnd.getTime() + value.seconds * 1000);
			setZoomStart(newStart);
			setZoomEnd(newEnd);
			onSearchChange({ rangeType: "span", seconds: value.seconds });
		} else if (value?.type === "range") {
			setZoomStart(value.startDate);
			setZoomEnd(value.endDate);
			onSearchChange({
				rangeType: "range",
				start: value.startDate.toISOString(),
				end: value.endDate.toISOString(),
			});
		}
	};

	const handleZoomChange = useCallback((start: Date, end: Date) => {
		setZoomStart(start);
		setZoomEnd(end);
	}, []);

	const handleSelectionChange = useCallback(
		(start: Date | null, end: Date | null) => {
			setSelectionStart(start);
			setSelectionEnd(end);
		},
		[],
	);

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
			<div className="flex flex-wrap gap-4">
				<Suspense fallback={<Skeleton className="h-10 w-48" />}>
					<EventsResourceFilter
						selectedResourceIds={search.resource ?? []}
						onResourceIdsChange={handleResourceIdsChange}
					/>
				</Suspense>
				<Suspense fallback={<Skeleton className="h-10 w-48" />}>
					<EventsTypeFilter
						filter={countFilter}
						selectedEventTypes={search.event ?? []}
						onEventTypesChange={handleEventTypesChange}
					/>
				</Suspense>
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

			{/* Chart - sticky when scrolling */}
			<Card
				className={cn(
					"sticky top-0 z-10 transition-shadow",
					isChartSticky && "shadow-lg",
				)}
			>
				<CardHeader className="pb-2">
					<CardTitle className="text-base">Event Activity</CardTitle>
				</CardHeader>
				<CardContent>
					<InteractiveEventsChart
						data={historyData}
						className="h-32"
						zoomStart={zoomStart}
						zoomEnd={zoomEnd}
						onZoomChange={handleZoomChange}
						onSelectionChange={handleSelectionChange}
						selectionStart={selectionStart}
						selectionEnd={selectionEnd}
					/>
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
