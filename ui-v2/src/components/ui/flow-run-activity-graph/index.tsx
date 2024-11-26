import { Bar, BarChart, Cell } from "recharts";
import { ChartContainer } from "@/components/ui/chart";
import type { components } from "@/api/prefect";
import { useEffect, useRef, useState } from "react";

interface CustomShapeProps {
	fill?: string;
	x?: number;
	y?: number;
	width?: number;
	height?: number;
	background?: boolean;
	className?: string;
	value?: number;
	radius?: number[];
}

const CustomBar = (props: CustomShapeProps) => {
	const minHeight = 6; // Minimum height for zero values
	const {
		x = 0,
		y = 0,
		width = 0,
		height = minHeight,
		radius = [0, 0, 0, 0],
		fill,
	} = props;

	return (
		<g>
			<rect
				x={x}
				y={y + height - Math.max(height, minHeight)}
				width={width}
				height={Math.max(height, minHeight)}
				rx={radius[0]}
				ry={radius[0]}
				fill={fill}
			/>
		</g>
	);
};

type FlowRunActivityGraphProps = {
	flowRuns: components["schemas"]["FlowRun"][];
	startDate: Date;
	endDate: Date;
	size?: "sm" | "md";
};

export const FlowRunActivityGraph = ({
	flowRuns,
	startDate,
	endDate,
	size = "md",
}: FlowRunActivityGraphProps) => {
	const barSize = size === "sm" ? 4 : 8;
	const barGap = size === "sm" ? 4 : 6;
	const containerRef = useRef<HTMLDivElement>(null);
	const [numberOfBars, setNumberOfBars] = useState(10);
	useEffect(() => {
		if (containerRef.current) {
			setNumberOfBars(
				Math.floor(
					containerRef.current.getBoundingClientRect().width /
						(barSize + barGap),
				),
			);
		}
	}, [barSize, barGap]);
	const buckets = organizeFlowRunsWithGaps(
		flowRuns,
		startDate,
		endDate,
		numberOfBars,
	);
	console.log(buckets.length);
	const data = buckets.map((flowRun) => ({
		value: flowRun?.total_run_time,
		id: flowRun?.id,
		stateType: flowRun?.state_type,
	}));
	return (
		<ChartContainer
			ref={containerRef}
			config={{
				activity: {
					label: "Activity",
					color: "hsl(142.1 76.2% 36.3%)",
				},
				inactivity: {
					label: "Inactivity",
					color: "hsl(210 40% 45%)",
				},
			}}
			className="h-24"
		>
			<BarChart
				data={data}
				margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
				barSize={barSize}
				barGap={barGap}
			>
				<Bar
					dataKey="value"
					shape={<CustomBar />}
					fill="var(--color-activity)"
					radius={[2, 2, 2, 2]}
				>
					{data.map((entry) => (
						<Cell
							key={`cell-${entry.id}`}
							fill={
								entry.stateType === "COMPLETED"
									? "var(--color-activity)"
									: "var(--color-inactivity)"
							}
						/>
					))}
				</Bar>
			</BarChart>
		</ChartContainer>
	);
};

function organizeFlowRunsWithGaps(
	flowRuns: components["schemas"]["FlowRun"][],
	startDate: Date,
	endDate: Date,
	numberOfBars: number,
): (components["schemas"]["FlowRun"] | null)[] {
	if (!startDate || !endDate) {
		return [];
	}

	const totalTime = endDate.getTime() - startDate.getTime();
	const bucketSize = totalTime / numberOfBars;
	const buckets: (components["schemas"]["FlowRun"] | null)[] = new Array(
		numberOfBars,
	).fill(null) as null[];
	const maxBucketIndex = buckets.length - 1;

	const isFutureTimeSpan = endDate.getTime() > new Date().getTime();

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
