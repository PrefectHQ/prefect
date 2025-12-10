import { useSuspenseQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Area, AreaChart } from "recharts";
import {
	buildTaskRunsHistoryQuery,
	type HistoryResponse,
} from "@/api/task-runs";
import { type ChartConfig, ChartContainer } from "@/components/ui/chart";
import {
	buildTaskRunsHistoryFilterFromDashboard,
	type TaskRunsTrendsFilter,
} from "./task-runs-history-filter";

type TaskRunsTrendsProps = {
	filter?: TaskRunsTrendsFilter;
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

export function TaskRunsTrends({ filter }: TaskRunsTrendsProps) {
	const historyFilter = useMemo(
		() => buildTaskRunsHistoryFilterFromDashboard(filter),
		[filter],
	);

	const { data: history } = useSuspenseQuery(
		buildTaskRunsHistoryQuery(historyFilter, 30000),
	);

	const chartData = useMemo(
		() => transformHistoryToChartData(history),
		[history],
	);

	const hasFailedData = chartData.some((point) => point.failed > 0);

	return (
		/* Break out of card padding (px-6 = 1.5rem × 2) */
		<div className="h-16 w-[calc(100%+3rem)] -mx-6">
			<ChartContainer config={chartConfig} className="h-full w-full">
				<AreaChart
					data={chartData}
					margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
				>
					<defs>
						<linearGradient id="completedGradient" x1="0" y1="1" x2="0" y2="0">
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
						<linearGradient id="failedGradient" x1="0" y1="1" x2="0" y2="0">
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
							fill="url(#failedGradient)"
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
						fill="url(#completedGradient)"
						dot={false}
						isAnimationActive={false}
					/>
				</AreaChart>
			</ChartContainer>
		</div>
	);
}
