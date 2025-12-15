import { useMemo } from "react";

/**
 * Available time intervals for chart bucketing (in seconds)
 */
const INTERVALS = [
	0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 20, 30, 60, 120, 300, 600,
	900, 1200, 1800, 3600, 7200, 14400, 21600, 43200, 86400, 172800, 604800,
	2592000, 10000,
];

const DESIRED_BUCKET_WIDTH_PX = 15;

export type TimeUnit = "second" | "minute" | "hour" | "day" | "week";

export type ChartInterval = {
	interval: number;
	unit: TimeUnit;
};

/**
 * Calculates the optimal time interval for chart bucketing based on
 * the date range and container width.
 *
 * @param startDate - Start of the date range
 * @param endDate - End of the date range
 * @param containerWidth - Width of the chart container in pixels
 * @returns Optimal interval and time unit for the API request
 */
export function useChartInterval(
	startDate: Date,
	endDate: Date,
	containerWidth: number,
): ChartInterval {
	return useMemo(() => {
		const rangeInSeconds = (endDate.getTime() - startDate.getTime()) / 1000;
		const desiredBuckets = Math.max(
			1,
			containerWidth / DESIRED_BUCKET_WIDTH_PX,
		);
		const goalInterval = rangeInSeconds / desiredBuckets;

		// Find the closest interval from the predefined list
		let bestInterval = INTERVALS[0];
		let bestDiff = Math.abs(goalInterval - bestInterval);

		for (const interval of INTERVALS) {
			const diff = Math.abs(goalInterval - interval);
			if (diff < bestDiff) {
				bestDiff = diff;
				bestInterval = interval;
			}
		}

		// Determine the appropriate time unit
		const unit = getTimeUnit(bestInterval);

		return { interval: bestInterval, unit };
	}, [startDate, endDate, containerWidth]);
}

function getTimeUnit(intervalSeconds: number): TimeUnit {
	if (intervalSeconds < 60) return "second";
	if (intervalSeconds < 3600) return "minute";
	if (intervalSeconds < 86400) return "hour";
	if (intervalSeconds < 604800) return "day";
	return "week";
}
