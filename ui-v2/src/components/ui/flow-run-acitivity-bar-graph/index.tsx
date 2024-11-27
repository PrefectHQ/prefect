import { Bar, BarChart, Cell } from "recharts";
import { ChartContainer, ChartTooltip } from "@/components/ui/chart";
import type { components } from "@/api/prefect";
import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../card";
import { ChevronRight } from "lucide-react";
import { StateBadge } from "../state-badge";

interface CustomShapeProps {
	fill?: string;
	x?: number;
	y?: number;
	width?: number;
	height?: number;
	radius?: number[];
}

const CustomBar = (props: CustomShapeProps) => {
	const minHeight = 4; // Minimum height for zero values
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

type EnrichedFlowRun = components["schemas"]["FlowRun"] & {
	deployment: components["schemas"]["DeploymentResponse"];
	flow: components["schemas"]["Flow"];
};

type FlowRunActivityBarChartProps = {
	enrichedFlowRuns: EnrichedFlowRun[];
	startDate: Date;
	endDate: Date;
	className?: string;
	barSize?: number;
	barGap?: number;
};

export const FlowRunActivityBarChart = ({
	enrichedFlowRuns,
	startDate,
	endDate,
	barSize = 4,
	barGap = 10,
	className,
}: FlowRunActivityBarChartProps) => {
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
		enrichedFlowRuns,
		startDate,
		endDate,
		numberOfBars,
	);

	const data = buckets.map((flowRun) => ({
		value: flowRun?.total_run_time,
		id: flowRun?.id,
		stateType: flowRun?.state_type,
		flowRun,
	}));
	return (
		<ChartContainer
			ref={containerRef}
			config={{
				inactivity: {
					color: "hsl(210 40% 45%)",
				},
			}}
			className={className}
		>
			<BarChart
				data={data}
				margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
				barSize={barSize}
				barCategoryGap={barGap}
			>
				<ChartTooltip
					content={<FlowRunTooltip />}
					position={{ y: 0 }}
					isAnimationActive={false}
				/>
				<Bar dataKey="value" shape={<CustomBar />} radius={[2, 2, 2, 2]}>
					{data.map((entry) => (
						<Cell
							key={`cell-${entry.id}`}
							fill={
								entry.stateType
									? `hsl(var(--state-${entry.stateType?.toLowerCase()}))`
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

const FlowRunTooltip = ({
	payload,
}: {
	active?: boolean;
	payload?: unknown[];
}) => {
	const flowRun = payload?.[0]?.payload?.flowRun as EnrichedFlowRun;
	if (!flowRun) {
		return null;
	}
	return (
		<Card>
			<CardHeader>
				<CardTitle className="text-lg flex items-center gap-1">
					<span className="font-medium">{flowRun.deployment.name}</span>
					<ChevronRight className="w-4 h-4" />
					<span className="font-medium">{flowRun.name}</span>
				</CardTitle>
				{flowRun.state && (
					<CardDescription>
						<StateBadge state={flowRun.state} />
					</CardDescription>
				)}
			</CardHeader>
			<CardContent>
			</CardContent>
		</Card>
	);
};
