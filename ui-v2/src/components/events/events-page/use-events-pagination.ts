import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
	buildEventsNextPageQuery,
	buildFilterEventsQuery,
	type Event,
	type EventsFilter,
} from "@/api/events";

const PAGE_SIZE = 50;

type UseEventsPaginationOptions = {
	filter: EventsFilter;
};

type UseEventsPaginationReturn = {
	events: Event[];
	currentPage: number;
	totalPages: number;
	total: number;
	isLoadingNextPage: boolean;
	goToPage: (page: number) => void;
	goToNextPage: () => void;
	goToPreviousPage: () => void;
};

/**
 * Hook for cursor-based pagination of events using a token vault pattern.
 *
 * The backend uses cursor-based pagination where each page response includes
 * a `next_page` URL containing a token to fetch the next page. This hook
 * manages these tokens in a "vault" (a Map) to enable bidirectional navigation.
 *
 * Key features:
 * - `tokenVault[n]` contains the token to fetch page `n+1`
 * - Clears token vault when filter changes (detected via JSON.stringify comparison)
 * - Stores next page tokens from API responses as they're received
 * - Uses `useQuery` for both the first page and subsequent pages
 *
 * @param options - Configuration options
 * @param options.filter - The events filter to apply
 * @returns Pagination state and navigation functions
 *
 * @example
 * ```tsx
 * const {
 *   events,
 *   currentPage,
 *   totalPages,
 *   isLoadingNextPage,
 *   goToPage,
 *   goToNextPage,
 *   goToPreviousPage,
 * } = useEventsPagination({ filter: myFilter });
 * ```
 */
export function useEventsPagination({
	filter,
}: UseEventsPaginationOptions): UseEventsPaginationReturn {
	const [currentPage, setCurrentPage] = useState(1);
	const tokenVault = useRef<Map<number, string>>(new Map());
	const previousFilterRef = useRef<string>(JSON.stringify(filter));

	// Reset pagination when filter changes
	useEffect(() => {
		const currentFilterString = JSON.stringify(filter);
		if (previousFilterRef.current !== currentFilterString) {
			tokenVault.current.clear();
			setCurrentPage(1);
			previousFilterRef.current = currentFilterString;
		}
	}, [filter]);

	// First page query - always fetches the first page
	const firstPageQuery = useQuery(buildFilterEventsQuery(filter));

	// Store the next_page token from first page response
	useEffect(() => {
		if (firstPageQuery.data?.next_page) {
			tokenVault.current.set(1, firstPageQuery.data.next_page);
		}
	}, [firstPageQuery.data?.next_page]);

	// Get the token for the current page (if not page 1)
	const currentPageToken =
		currentPage > 1 ? tokenVault.current.get(currentPage - 1) : null;

	// Subsequent page query - only enabled when we have a token and not on page 1
	const nextPageQuery = useQuery({
		...buildEventsNextPageQuery(currentPageToken ?? ""),
		enabled: currentPage > 1 && !!currentPageToken,
	});

	// Store the next_page token from subsequent page responses
	useEffect(() => {
		if (nextPageQuery.data?.next_page && currentPage > 1) {
			tokenVault.current.set(currentPage, nextPageQuery.data.next_page);
		}
	}, [nextPageQuery.data?.next_page, currentPage]);

	// Calculate total pages from the first page total count
	const total = firstPageQuery.data?.total ?? 0;
	const totalPages = Math.ceil(total / PAGE_SIZE);

	// Determine current events based on which page we're on
	const events =
		currentPage === 1
			? (firstPageQuery.data?.events ?? [])
			: (nextPageQuery.data?.events ?? firstPageQuery.data?.events ?? []);

	const isLoadingNextPage = currentPage > 1 && nextPageQuery.isLoading;

	const goToPage = (page: number) => {
		if (page < 1 || page > totalPages) return;
		if (page > 1 && !tokenVault.current.has(page - 1)) {
			return;
		}
		setCurrentPage(page);
	};

	const goToNextPage = () => {
		if (currentPage < totalPages && tokenVault.current.has(currentPage)) {
			setCurrentPage(currentPage + 1);
		}
	};

	const goToPreviousPage = () => {
		if (currentPage > 1) {
			setCurrentPage(currentPage - 1);
		}
	};

	return {
		events,
		currentPage,
		totalPages,
		total,
		isLoadingNextPage,
		goToPage,
		goToNextPage,
		goToPreviousPage,
	};
}
