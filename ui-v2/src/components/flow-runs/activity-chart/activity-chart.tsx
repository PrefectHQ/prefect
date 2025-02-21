import { FlowRun } from "@/api/flow-runs";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Typography } from "@/components/ui/typography";
import React, { useCallback, useEffect, useMemo } from "react";
import { FlowRunCell } from "./flowRunCell";

export type FlowRunsBarChartProps = {
	startWindow?: Date;
	endWindow?: Date;
	mini?: boolean;
	flowRuns: FlowRun[];
	flowName: string;
	className?: string;
};

const FlowRunsBarChart: React.FC<FlowRunsBarChartProps> = ({
	startWindow,
	endWindow,
	mini = false,
	flowRuns,
	flowName,
	className,
}) => {
	const divRef = React.useRef<HTMLDivElement>(null);
	const [width, setWidth] = React.useState(400);
	const [height, setHeight] = React.useState(400);
	const barWidth = useMemo(() => {
		return mini ? 6 : 12;
	}, [mini]);

	const bars = Math.floor(width / barWidth);

	const maxValue = useMemo(() => {
		return Math.max(
			...flowRuns.map((flowRun) => flowRun.estimated_run_time ?? 0),
		);
	}, [flowRuns]);

	const findWindow = useCallback(() => {
		if (divRef.current) {
			setWidth(divRef.current.clientWidth);
			setHeight(divRef.current.clientHeight - 25);
		}
	}, [divRef]);

	useEffect(() => {
		findWindow();
		window.addEventListener("resize", findWindow);
		return () => {
			window.removeEventListener("resize", findWindow);
		};
	}, [divRef, findWindow]);

	const mapStateToColor = (state: string) => {
		switch (state) {
			case "COMPLETED":
				return "#4caf50";
			case "FAILED":
				return "#f44336";
			case "RUNNING":
				return "#ff9800";
			case "CANCELED":
				return "#9e9e9e";
			default:
				return "#6f727b";
		}
	};

	// Organize flow runs with gaps
	const organizeFlowRunsWithGaps = useCallback(
		(runs: FlowRun[]): (FlowRun | null)[] => {
			if (!startWindow || !endWindow) {
				return [];
			}
			const buckets: (FlowRun | null)[] = new Array<FlowRun | null>(bars).fill(
				null,
			);
			const maxBucketIndex = buckets.length - 1;

			const isFutureTimeSpan = endWindow.getTime() > new Date().getTime();
			const bucketIncrementDirection = isFutureTimeSpan ? 1 : -1;

			const sortedRuns = isFutureTimeSpan
				? [...runs].sort((a, b) => {
						const aStartTime = new Date(
							a.start_time ?? a.expected_start_time ?? "",
						);
						const bStartTime = new Date(
							b.start_time ?? b.expected_start_time ?? "",
						);
						if (!aStartTime || !bStartTime) return 0;
						return aStartTime.getTime() - bStartTime.getTime();
					})
				: runs;

			const getEmptyBucket = (index: number): number | null => {
				console.log("index", index);
				if (index < 0) return null;
				if (buckets[index])
					return getEmptyBucket(index + bucketIncrementDirection);
				return index;
			};

			sortedRuns.forEach((flowRun) => {
				const startTime = new Date(
					flowRun.start_time ?? flowRun.expected_start_time ?? "",
				);
				if (!startTime) return;

				const bucketIndex = Math.min(
					Math.floor((endWindow.getTime() - startTime.getTime()) / bars),
					maxBucketIndex,
				);

				const emptyBucketIndex = getEmptyBucket(bucketIndex);
				if (emptyBucketIndex !== null) {
					buckets[emptyBucketIndex] = flowRun;
				}
			});

			return buckets;
		},
		[startWindow, endWindow, bars],
	);

	const barFlowRuns: (FlowRun | null)[] = useMemo(() => {
		const runsWithGaps = organizeFlowRunsWithGaps(flowRuns);
		return runsWithGaps;
	}, [flowRuns, organizeFlowRunsWithGaps]);

	const calcHeight = useCallback(
		(flowRun: FlowRun) => {
			const estimatedRunTime = flowRun.estimated_run_time ?? 0;
			const barHeight = (estimatedRunTime / maxValue) * height;
			return `${barHeight}px`;
		},
		[maxValue, height],
	);

	return (
		<div className={`w-full h-full ${className}`}>
			<TooltipProvider>
				<div className="w-full h-full flex flex-col p-4 border rounded-lg">
					<div className="flex justify-between">
						<Typography variant="body" className="text-black font-bold">
							Flow Runs
						</Typography>
						<Typography variant="bodySmall" className="text-black">
							<span className="font-bold">{flowRuns.length}</span> runs
						</Typography>
					</div>
					<div ref={divRef} className="w-full h-full flex items-end">
						{barFlowRuns.map((flowRun, index) => (
							<FlowRunCell
								key={index}
								width={`${barWidth}px`}
								height={flowRun ? calcHeight(flowRun) : "5px"}
								flowName={flowName}
								flowRun={flowRun}
								color={
									flowRun
										? mapStateToColor(flowRun.state_type ?? "")
										: "#6f727b"
								}
							/>
						))}
					</div>
				</div>
			</TooltipProvider>
		</div>
	);
};

export default FlowRunsBarChart;
