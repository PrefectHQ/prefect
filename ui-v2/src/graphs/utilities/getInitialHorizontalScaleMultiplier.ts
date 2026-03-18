import { differenceInSeconds } from "date-fns";
import { DEFAULT_TIME_COLUMN_SIZE_PIXELS } from "@/graphs/consts";
import type { RunGraphData, RunGraphStyles } from "@/graphs/models/RunGraph";

export function getInitialHorizontalScaleMultiplier(
	{ start_time, end_time, nodes }: RunGraphData,
	styles: Required<RunGraphStyles>,
	aspectRatio: number,
): number {
	const seconds = Math.max(
		differenceInSeconds(end_time ?? new Date(), start_time),
		1,
	);

	const nodeHeight = styles.nodeHeight + styles.rowGap;
	const apxConcurrencyFactor = 0.5;
	const emptyNodesHeightMultiplier = 4;

	const apxNodesHeight =
		nodes.size > 0
			? nodes.size * nodeHeight * apxConcurrencyFactor
			: nodeHeight * emptyNodesHeightMultiplier;

	const widthWeWant = apxNodesHeight * aspectRatio;

	const idealMultiplier =
		widthWeWant / (seconds * DEFAULT_TIME_COLUMN_SIZE_PIXELS);

	return idealMultiplier;
}
