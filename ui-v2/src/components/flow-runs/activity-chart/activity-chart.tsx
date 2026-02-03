import { cva } from "class-variance-authority";
import React, { useCallback, useEffect, useMemo } from "react";
import type { FlowRun } from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import { TooltipProvider } from "@/components/ui/tooltip";
import { FlowRunCell } from "./flowRunCell";

export type FlowRunsBarChartProps = {
	startWindow?: Date;
	endWindow?: Date;
	mini?: boolean;
	flowRuns: FlowRun[];
	flowName: string;
	className?: string;
};

const FlowRunsBarChart = ({
	startWindow,
	endWindow,
	mini = false,
	flowRuns,
	flowName,
	className,
}: FlowRunsBarChartProps) => {
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
	}, []);

	useEffect(() => {
		findWindow();
		window.addEventListener("resize", findWindow);
		return () => {
			window.removeEventListener("resize", findWindow);
		};
	}, [findWindow]);

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

			const isFutureTimeSpan = endWindow.getTime() > Date.now();
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
				if (index < 0) return null;
				if (buckets[index])
					return getEmptyBucket(index + bucketIncrementDirection);
				return index;
			};

			for (const flowRun of sortedRuns) {
				const startTime = new Date(
					flowRun.start_time ?? flowRun.expected_start_time ?? "",
				);
				if (!startTime) continue;

				const bucketIndex = Math.min(
					Math.floor((endWindow.getTime() - startTime.getTime()) / bars),
					maxBucketIndex,
				);

				const emptyBucketIndex = getEmptyBucket(bucketIndex);
				if (emptyBucketIndex !== null) {
					buckets[emptyBucketIndex] = flowRun;
				}
			}

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

	const stateBadgeVariants = cva("gap-1", {
		variants: {
			state: {
				COMPLETED: "bg-[var(--state-completed-500)]",
				FAILED: "bg-[var(--state-failed-500)]",
				RUNNING: "bg-[var(--state-running-500)]",
				CANCELLED: "bg-[var(--state-cancelled-500)]",
				CANCELLING: "bg-[var(--state-cancelling-500)]",
				CRASHED: "bg-[var(--state-crashed-500)]",
				PAUSED: "bg-[var(--state-paused-500)]",
				PENDING: "bg-[var(--state-pending-500)]",
				SCHEDULED: "bg-[var(--state-scheduled-500)]",
			} satisfies Record<components["schemas"]["StateType"], string>,
		},
	});

	return (
		<div className={`w-full h-full ${className}`}>
			<TooltipProvider>
				<div className="w-full h-full flex flex-col p-4 border rounded-lg">
					<div className="flex justify-between">
						<p className="text-base text-foreground font-bold">Flow Runs</p>
						<p className="text-sm text-foreground">
							<span className="font-bold">{flowRuns.length}</span> runs
						</p>
					</div>
					<div ref={divRef} className="w-full h-full flex items-end">
						{barFlowRuns.map((flowRun, index) => (
							<FlowRunCell
								key={flowRun?.id ?? index}
								width={`${barWidth}px`}
								height={flowRun ? calcHeight(flowRun) : "5px"}
								flowName={flowName}
								flowRun={flowRun}
								className={stateBadgeVariants({
									state: flowRun?.state?.type ?? "PENDING",
								})}
							/>
						))}
					</div>
				</div>
			</TooltipProvider>
		</div>
	);
};

export default FlowRunsBarChart;
