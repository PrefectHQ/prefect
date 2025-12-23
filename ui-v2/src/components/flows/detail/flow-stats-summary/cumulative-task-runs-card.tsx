import { useSuspenseQueries } from "@tanstack/react-query";
import { useMemo } from "react";
import { Area, AreaChart } from "recharts";
import {
	buildCountTaskRunsQuery,
	buildTaskRunsHistoryQuery,
	type HistoryResponse,
} from "@/api/task-runs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type ChartConfig, ChartContainer } from "@/components/ui/chart";
import {
	buildCompletedTaskRunsCountFilter,
	buildFailedTaskRunsCountFilter,
	buildRunningTaskRunsCountFilter,
	buildTaskRunsHistoryFilterForFlow,
	buildTotalTaskRunsCountFilter,
} from "./query-filters";

const REFETCH_INTERVAL = 30_000;

type CumulativeTaskRunsCardProps = {
	flowId: string;
};

type ChartDataPoint = {
	timestamp: string;
	completed: number;
	failed: number;
};

const chartConfig = {
	completed: {
		label: "Completed",
		color: "hsl(142.1 76.2% 36.3%)",
	},
	failed: {
		label: "Failed",
		color: "hsl(0 84.2% 60.2%)",
	},
} satisfies ChartConfig;

const transformHistoryToChartData = (
	history: HistoryResponse[],
): ChartDataPoint[] => {
	const chartData: ChartDataPoint[] = [];
	let cumulativeCompleted = 0;
	let cumulativeFailed = 0;

	for (const item of history) {
		let completedCount = 0;
		let failedCount = 0;

		for (const state of item.states) {
			if (state.state_type === "COMPLETED") {
				completedCount += state.count_runs;
			} else if (
				state.state_type === "FAILED" ||
				state.state_type === "CRASHED"
			) {
				failedCount += state.count_runs;
			}
		}

		cumulativeCompleted += completedCount;
		cumulativeFailed += failedCount;

		chartData.push({
			timestamp: item.interval_start,
			completed: cumulativeCompleted,
			failed: cumulativeFailed,
		});
	}

	return chartData;
};

export function CumulativeTaskRunsCard({
	flowId,
}: CumulativeTaskRunsCardProps) {
	const [
		{ data: total },
		{ data: completed },
		{ data: failed },
		{ data: running },
		{ data: history },
	] = useSuspenseQueries({
		queries: [
			buildCountTaskRunsQuery(
				buildTotalTaskRunsCountFilter(flowId),
				REFETCH_INTERVAL,
			),
			buildCountTaskRunsQuery(
				buildCompletedTaskRunsCountFilter(flowId),
				REFETCH_INTERVAL,
			),
			buildCountTaskRunsQuery(
				buildFailedTaskRunsCountFilter(flowId),
				REFETCH_INTERVAL,
			),
			buildCountTaskRunsQuery(
				buildRunningTaskRunsCountFilter(flowId),
				REFETCH_INTERVAL,
			),
			buildTaskRunsHistoryQuery(
				buildTaskRunsHistoryFilterForFlow(flowId),
				REFETCH_INTERVAL,
			),
		],
	});

	const chartData = useMemo(
		() => transformHistoryToChartData(history),
		[history],
	);

	const hasFailedData = chartData.some((point) => point.failed > 0);

	const percentComparisonTotal = total - running;
	const completedPercentage =
		percentComparisonTotal > 0
			? ((completed / percentComparisonTotal) * 100).toFixed(0)
			: "0";
	const failedPercentage =
		percentComparisonTotal > 0
			? ((failed / percentComparisonTotal) * 100).toFixed(1)
			: "0";

	return (
		<Card className="flex-1 relative overflow-hidden pb-20">
			<CardHeader className="pb-2">
				<CardTitle>Task Runs</CardTitle>
			</CardHeader>
			<CardContent>
				<div className="grid gap-1">
					<div className="inline-flex items-end gap-1 text-base">
						<span className="font-semibold">{total}</span>
					</div>
					{running > 0 && (
						<div className="inline-flex items-end gap-1 text-sm">
							<span className="font-semibold text-blue-600">{running}</span>
							<span className="text-muted-foreground">Running</span>
						</div>
					)}
					<div className="inline-flex items-end gap-1 text-sm">
						<span className="font-semibold text-green-600">{completed}</span>
						<span className="text-muted-foreground">Completed</span>
						<span className="text-green-600">{completedPercentage}%</span>
					</div>
					{failed > 0 && (
						<div className="inline-flex items-end gap-1 text-sm">
							<span className="font-semibold text-red-600">{failed}</span>
							<span className="text-muted-foreground">Failed</span>
							<span className="text-red-600">{failedPercentage}%</span>
						</div>
					)}
				</div>
			</CardContent>
			<div className="absolute bottom-4 left-0 right-0 h-16">
				<ChartContainer config={chartConfig} className="h-full w-full">
					<AreaChart
						data={chartData}
						margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
					>
						<defs>
							<linearGradient
								id="completedGradientFlow"
								x1="0"
								y1="1"
								x2="0"
								y2="0"
							>
								<stop
									offset="0%"
									stopColor="var(--color-completed)"
									stopOpacity={0}
								/>
								<stop
									offset="100%"
									stopColor="var(--color-completed)"
									stopOpacity={0.3}
								/>
							</linearGradient>
							<linearGradient
								id="failedGradientFlow"
								x1="0"
								y1="1"
								x2="0"
								y2="0"
							>
								<stop
									offset="0%"
									stopColor="var(--color-failed)"
									stopOpacity={0}
								/>
								<stop
									offset="100%"
									stopColor="var(--color-failed)"
									stopOpacity={0.3}
								/>
							</linearGradient>
						</defs>
						{hasFailedData && (
							<Area
								type="monotone"
								dataKey="failed"
								stroke="var(--color-failed)"
								strokeWidth={2}
								activeDot={false}
								fill="url(#failedGradientFlow)"
								dot={false}
								isAnimationActive={false}
							/>
						)}
						<Area
							type="monotone"
							dataKey="completed"
							stroke="var(--color-completed)"
							strokeWidth={2}
							activeDot={false}
							fill="url(#completedGradientFlow)"
							dot={false}
							isAnimationActive={false}
						/>
					</AreaChart>
				</ChartContainer>
			</div>
		</Card>
	);
}
