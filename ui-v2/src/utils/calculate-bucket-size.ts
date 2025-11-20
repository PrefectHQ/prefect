/**
 * Calculate the appropriate time bucket size based on date range
 * @param startDate - Start of the date range
 * @param endDate - End of the date range
 * @returns 'hour' for <3 days, 'day' for <30 days, 'week' for ≥30 days
 */
export function calculateBucketSize(
	startDate: Date,
	endDate: Date,
): "hour" | "day" | "week" {
	const diffMs = endDate.getTime() - startDate.getTime();
	const diffDays = diffMs / (1000 * 60 * 60 * 24);

	if (diffDays < 3) return "hour";
	if (diffDays < 30) return "day";
	return "week";
}
