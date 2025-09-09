import { useCallback, useMemo } from "react";
import { z } from "zod";
import type { DateRangeValue } from "./date-range-select";

/**
 * Schema for validating dashboard filter URL search parameters
 * @property {string[]} tags - Array of tags to filter by
 * @property {boolean} hideSubflows - Whether to hide subflow runs
 * @property {object} dateRange - Date range configuration
 */
const dashboardFilterSchema = z.object({
	tags: z.array(z.string()).optional().default([]).catch([]),
	hideSubflows: z.boolean().optional().default(false).catch(false),
	// Simplified date range - we'll serialize the DateRangeValue as needed
	dateRangeType: z.enum(["span", "range"]).optional().catch(undefined),
	dateRangeSeconds: z.number().optional().catch(undefined),
	dateRangeStart: z.string().optional().catch(undefined),
	dateRangeEnd: z.string().optional().catch(undefined),
});

export type DashboardFilterSearchParams = z.infer<typeof dashboardFilterSchema>;

export type DashboardFilter = {
	tags: string[];
	hideSubflows: boolean;
	dateRange: DateRangeValue;
};

/**
 * Hook for managing dashboard filter state with URL synchronization
 * Provides filter values and handlers for updating filters through URL parameters
 */
export const useDashboardFilter = () => {
	// This would be used in the dashboard route - for now we'll create a placeholder
	// that would be replaced when integrated with the actual route
	const search = useMockSearch(); // Placeholder - replace with Route.useSearch() in dashboard
	const navigate = useMockNavigate(); // Placeholder - replace with Route.useNavigate() in dashboard

	// Parse the date range from URL parameters
	const dateRange = useMemo((): DateRangeValue => {
		if (!search.dateRangeType) return null;

		if (
			search.dateRangeType === "span" &&
			search.dateRangeSeconds !== undefined
		) {
			return { type: "span", seconds: search.dateRangeSeconds };
		}

		if (
			search.dateRangeType === "range" &&
			search.dateRangeStart &&
			search.dateRangeEnd
		) {
			return {
				type: "range",
				startDate: new Date(search.dateRangeStart),
				endDate: new Date(search.dateRangeEnd),
			};
		}

		return null;
	}, [
		search.dateRangeType,
		search.dateRangeSeconds,
		search.dateRangeStart,
		search.dateRangeEnd,
	]);

	const filter: DashboardFilter = useMemo(
		() => ({
			tags: search.tags,
			hideSubflows: search.hideSubflows,
			dateRange,
		}),
		[search.tags, search.hideSubflows, dateRange],
	);

	// Update tags filter
	const updateTags = useCallback(
		(tags: string[]) => {
			navigate({
				search: (prev) => ({
					...prev,
					tags: tags.length > 0 ? tags : undefined,
				}),
			});
		},
		[navigate],
	);

	// Update subflows toggle
	const updateHideSubflows = useCallback(
		(hideSubflows: boolean) => {
			navigate({
				search: (prev) => ({
					...prev,
					hideSubflows: hideSubflows || undefined,
				}),
			});
		},
		[navigate],
	);

	// Update date range
	const updateDateRange = useCallback(
		(dateRange: DateRangeValue) => {
			navigate({
				search: (prev) => {
					if (!dateRange) {
						const {
							dateRangeType: _dateRangeType,
							dateRangeSeconds: _dateRangeSeconds,
							dateRangeStart: _dateRangeStart,
							dateRangeEnd: _dateRangeEnd,
							...rest
						} = prev;
						return rest;
					}

					if (dateRange.type === "span") {
						return {
							...prev,
							dateRangeType: "span" as const,
							dateRangeSeconds: dateRange.seconds,
							dateRangeStart: undefined,
							dateRangeEnd: undefined,
						};
					}

					if (dateRange.type === "range") {
						return {
							...prev,
							dateRangeType: "range" as const,
							dateRangeStart: dateRange.startDate.toISOString(),
							dateRangeEnd: dateRange.endDate.toISOString(),
							dateRangeSeconds: undefined,
						};
					}

					return prev;
				},
			});
		},
		[navigate],
	);

	return {
		filter,
		updateTags,
		updateHideSubflows,
		updateDateRange,
	};
};

// Temporary mock functions - these would be replaced with actual route hooks
function useMockSearch(): DashboardFilterSearchParams {
	return {
		tags: [],
		hideSubflows: false,
		dateRangeType: undefined,
		dateRangeSeconds: undefined,
		dateRangeStart: undefined,
		dateRangeEnd: undefined,
	};
}

function useMockNavigate() {
	return ({
		search,
	}: {
		search: (
			prev: DashboardFilterSearchParams,
		) => Partial<DashboardFilterSearchParams>;
	}) => {
		const mockPrev: DashboardFilterSearchParams = {
			tags: [],
			hideSubflows: false,
			dateRangeType: undefined,
			dateRangeSeconds: undefined,
			dateRangeStart: undefined,
			dateRangeEnd: undefined,
		};
		console.log("Navigate called with:", search(mockPrev));
	};
}

export { dashboardFilterSchema };
