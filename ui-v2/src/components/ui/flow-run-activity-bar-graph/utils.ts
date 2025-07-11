import type { components } from "@/api/prefect";

/**
 * Organizes flow runs into time-based buckets with gaps for visualization.
 *
 * @param flowRuns - Array of flow runs to organize
 * @param startDate - Start date of the time range to organize runs into
 * @param endDate - End date of the time range to organize runs into
 * @param numberOfBuckets - Number of buckets/bars to divide the time range into
 * @returns Array of flow runs or null values representing empty buckets. The length matches numberOfBars.
 *
 * This function:
 * 1. Divides the time range into equal-sized buckets
 * 2. Sorts runs by start time if the time range extends into the future
 * 3. Places each run into an appropriate bucket, maintaining order and gaps
 * 4. Returns null for buckets with no runs
 */
export function organizeFlowRunsWithGaps(
	flowRuns: components["schemas"]["FlowRun"][],
	startDate: Date,
	endDate: Date,
	numberOfBuckets: number,
): (components["schemas"]["FlowRun"] | null)[] {
	if (!startDate || !endDate) {
		return [];
	}

	if (flowRuns.length > numberOfBuckets) {
		throw new Error(
			`Number of flow runs (${flowRuns.length}) is greater than the number of buckets (${numberOfBuckets})`,
		);
	}

	const totalTime = endDate.getTime() - startDate.getTime();
	const bucketSize = totalTime / numberOfBuckets;
	const buckets: (components["schemas"]["FlowRun"] | null)[] = new Array(
		numberOfBuckets,
	).fill(null) as null[];
	const maxBucketIndex = buckets.length - 1;

	const isFutureTimeSpan = endDate.getTime() > Date.now();

	const bucketIncrementDirection = isFutureTimeSpan ? 1 : -1;
	const sortedRuns = isFutureTimeSpan
		? flowRuns.sort((runA, runB) => {
				const aStartTime = runA.start_time
					? new Date(runA.start_time)
					: runA.expected_start_time
						? new Date(runA.expected_start_time)
						: null;
				const bStartTime = runB.start_time
					? new Date(runB.start_time)
					: runB.expected_start_time
						? new Date(runB.expected_start_time)
						: null;

				if (!aStartTime || !bStartTime) {
					return 0;
				}

				return aStartTime.getTime() - bStartTime.getTime();
			})
		: flowRuns;

	function getEmptyBucket(index: number): number | null {
		if (index < 0) {
			return null;
		}

		if (buckets[index]) {
			return getEmptyBucket(index + bucketIncrementDirection);
		}

		return index;
	}

	for (const flowRun of sortedRuns) {
		const startTime = flowRun.start_time
			? new Date(flowRun.start_time)
			: flowRun.expected_start_time
				? new Date(flowRun.expected_start_time)
				: null;

		if (!startTime) {
			continue;
		}

		const bucketIndex = Math.min(
			Math.floor((startTime.getTime() - startDate.getTime()) / bucketSize),
			maxBucketIndex,
		);
		const emptyBucketIndex = getEmptyBucket(bucketIndex);

		if (emptyBucketIndex === null) {
			continue;
		}

		buckets[emptyBucketIndex] = flowRun;
	}

	return buckets;
}
