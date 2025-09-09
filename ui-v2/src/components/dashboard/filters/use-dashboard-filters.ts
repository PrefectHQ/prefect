import { useNavigate, useSearch } from "@tanstack/react-router";
import { useMemo } from "react";
import type { DashboardFilter, DateRangeSelectValue } from "./types";

/**
 * URL search parameter schema for dashboard filters
 */
type DashboardSearchParams = {
	range?: string;
	tags?: string[];
	hideSubflows?: boolean;
};

/**
 * Default dashboard filter values
 */
const DEFAULT_FILTER: DashboardFilter = {
	range: { type: "span", seconds: -86400 }, // Last 24 hours
	tags: [],
	hideSubflows: undefined,
};

/**
 * Serializes a DateRangeSelectValue to a URL-safe string
 */
function serializeDateRange(value: DateRangeSelectValue): string | undefined {
	if (!value) return undefined;

	switch (value.type) {
		case "span":
			return `span:${value.seconds}`;
		case "range":
			return `range:${value.startDate.getTime()}:${value.endDate.getTime()}`;
		case "period":
			return `period:${value.period}`;
		case "around":
			return `around:${value.date.getTime()}:${value.quantity}:${value.unit}`;
		default:
			return undefined;
	}
}

/**
 * Deserializes a URL-safe string to a DateRangeSelectValue
 */
function deserializeDateRange(value?: string): DateRangeSelectValue {
	if (!value) return DEFAULT_FILTER.range;

	const [type, ...parts] = value.split(":");

	switch (type) {
		case "span":
			return { type: "span", seconds: Number(parts[0]) };
		case "range":
			return {
				type: "range",
				startDate: new Date(Number(parts[0])),
				endDate: new Date(Number(parts[1])),
			};
		case "period":
			return { type: "period", period: parts[0] as "Today" };
		case "around":
			return {
				type: "around",
				date: new Date(Number(parts[0])),
				quantity: Number(parts[1]),
				unit: parts[2] as "second" | "minute" | "hour" | "day",
			};
		default:
			return DEFAULT_FILTER.range;
	}
}

/**
 * Custom hook for managing dashboard filter state with URL persistence
 *
 * This hook provides:
 * - Current filter values from URL parameters
 * - Functions to update individual filter values
 * - Automatic URL synchronization
 *
 * @returns Object containing current filters and update functions
 *
 * @example
 * ```tsx
 * function DashboardFilters() {
 *   const {
 *     filter,
 *     updateDateRange,
 *     updateTags,
 *     updateHideSubflows,
 *     resetFilters
 *   } = useDashboardFilters();
 *
 *   return (
 *     <div>
 *       <DateRangeSelect
 *         value={filter.range}
 *         onValueChange={updateDateRange}
 *       />
 *       <FlowRunTagsInput
 *         value={filter.tags}
 *         onChange={updateTags}
 *       />
 *       <SubflowToggle
 *         value={filter.hideSubflows}
 *         onChange={updateHideSubflows}
 *       />
 *     </div>
 *   );
 * }
 * ```
 */
export function useDashboardFilters() {
	const navigate = useNavigate();
	const search = useSearch({ strict: false }) as DashboardSearchParams;

	// Parse current filters from URL search params
	const filter = useMemo(
		(): DashboardFilter => ({
			range: deserializeDateRange(search.range),
			tags: search.tags || [],
			hideSubflows: search.hideSubflows,
		}),
		[search.range, search.tags, search.hideSubflows],
	);

	/**
	 * Updates the date range filter
	 */
	const updateDateRange = (range: DateRangeSelectValue) => {
		navigate({
			search: (prev) => ({
				...prev,
				range: serializeDateRange(range),
			}),
			replace: true,
		});
	};

	/**
	 * Updates the tags filter
	 */
	const updateTags = (tags: string[]) => {
		navigate({
			search: (prev) => ({
				...prev,
				tags: tags.length > 0 ? tags : undefined,
			}),
			replace: true,
		});
	};

	/**
	 * Updates the hide subflows filter
	 */
	const updateHideSubflows = (hideSubflows: boolean) => {
		navigate({
			search: (prev) => ({
				...prev,
				hideSubflows: hideSubflows || undefined,
			}),
			replace: true,
		});
	};

	/**
	 * Resets all filters to their default values
	 */
	const resetFilters = () => {
		navigate({
			search: {},
			replace: true,
		});
	};

	/**
	 * Transforms the dashboard filter into a format suitable for flow runs API
	 */
	const getFlowRunsFilter = () => {
		const range = filter.range;
		let startDate: Date | undefined;
		let endDate: Date | undefined;

		if (range) {
			const now = new Date();
			switch (range.type) {
				case "span":
					startDate = new Date(now.getTime() + range.seconds * 1000);
					endDate = now;
					break;
				case "range":
					startDate = range.startDate;
					endDate = range.endDate;
					break;
				case "period":
					if (range.period === "Today") {
						startDate = new Date(
							now.getFullYear(),
							now.getMonth(),
							now.getDate(),
						);
						endDate = new Date(
							now.getFullYear(),
							now.getMonth(),
							now.getDate() + 1,
						);
					}
					break;
				case "around": {
					let secondsAmount = range.quantity;
					switch (range.unit) {
						case "minute":
							secondsAmount *= 60;
							break;
						case "hour":
							secondsAmount *= 3600;
							break;
						case "day":
							secondsAmount *= 86400;
							break;
					}
					startDate = new Date(range.date.getTime() - secondsAmount * 1000);
					endDate = new Date(range.date.getTime() + secondsAmount * 1000);
					break;
				}
			}
		}

		return {
			flowRuns: {
				...(startDate && { expectedStartTimeAfter: startDate.toISOString() }),
				...(endDate && { expectedStartTimeBefore: endDate.toISOString() }),
				...(filter.tags.length > 0 && {
					tags: { operator: "and_" as const, all_: filter.tags },
				}),
				...(filter.hideSubflows && { parentTaskRunIdNull: true }),
			},
		};
	};

	return {
		filter,
		updateDateRange,
		updateTags,
		updateHideSubflows,
		resetFilters,
		getFlowRunsFilter,
	};
}
