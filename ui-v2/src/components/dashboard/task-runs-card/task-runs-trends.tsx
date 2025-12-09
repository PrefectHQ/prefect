import { useSuspenseQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import {
	buildTaskRunsHistoryQuery,
	type HistoryResponse,
	type TaskRunsHistoryFilter,
} from "@/api/task-runs";
import {
	type ChartConfig,
	ChartContainer,
	ChartTooltip,
	ChartTooltipContent,
} from "@/components/ui/chart";

type TaskRunsTrendsProps = {
	filter?: {
		startDate?: string;
		endDate?: string;
		tags?: string[];
		hideSubflows?: boolean;
	};
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

const formatTimestamp = (timestamp: string): string => {
	const date = new Date(timestamp);
	return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

export function TaskRunsTrends({ filter }: TaskRunsTrendsProps) {
	const historyFilter: TaskRunsHistoryFilter = useMemo(() => {
		const now = new Date();
		const startDate = filter?.startDate
			? new Date(filter.startDate)
			: new Date(now.getTime() - 24 * 60 * 60 * 1000);
		const endDate = filter?.endDate ? new Date(filter.endDate) : now;

		const history_start = startDate.toISOString();
		const history_end = endDate.toISOString();
		const timeSpanInSeconds = Math.floor(
			(endDate.getTime() - startDate.getTime()) / 1000,
		);
		const historyInterval = Math.max(1, Math.floor(timeSpanInSeconds / 20));

		// Build filter matching Vue's mapTaskRunsHistoryFilter
		// Vue always includes flow_runs and task_runs with start_time filter
		const baseFilter: TaskRunsHistoryFilter = {
			history_start,
			history_end,
			history_interval_seconds: historyInterval,
			// Always include flow_runs (matches Vue's behavior - empty object when no filters)
			flow_runs: {
				operator: "and_",
			},
			// Always include task_runs with start_time filter (matches Vue's mapTaskRunFilter)
			task_runs: {
				operator: "and_",
				start_time: {
					after_: history_start,
					before_: history_end,
				},
			},
		};

		// Add tags filter on flow_runs (matching Vue's flowRuns.tags.anyName)
		if (filter?.tags && filter.tags.length > 0) {
			baseFilter.flow_runs = {
				...baseFilter.flow_runs,
				tags: {
					operator: "and_",
					any_: filter.tags,
				},
			};
		}

		// Add hideSubflows filter (matching Vue's flowRuns.parentTaskRunIdNull)
		if (filter?.hideSubflows) {
			baseFilter.flow_runs = {
				...baseFilter.flow_runs,
				parent_task_run_id: {
					operator: "and_",
					is_null_: true,
				},
			};
		}

		return baseFilter;
	}, [filter?.startDate, filter?.endDate, filter?.tags, filter?.hideSubflows]);

	const { data: history } = useSuspenseQuery(
		buildTaskRunsHistoryQuery(historyFilter, 30000),
	);

	const chartData = useMemo(
		() => transformHistoryToChartData(history),
		[history],
	);

	const hasData = chartData.some(
		(point) => point.completed > 0 || point.failed > 0,
	);

	if (!hasData) {
		return null;
	}

	return (
		<div className="h-32 w-full">
			<ChartContainer config={chartConfig} className="h-full w-full">
				<LineChart
					data={chartData}
					margin={{ top: 5, right: 10, bottom: 5, left: 10 }}
				>
					<CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
					<XAxis
						dataKey="timestamp"
						tickFormatter={formatTimestamp}
						tick={{ fontSize: 10 }}
						tickLine={false}
						axisLine={false}
						className="text-muted-foreground"
					/>
					<YAxis
						tick={{ fontSize: 10 }}
						tickLine={false}
						axisLine={false}
						className="text-muted-foreground"
						allowDecimals={false}
					/>
					<ChartTooltip
						content={
							<ChartTooltipContent
								labelFormatter={(value: string) => {
									const date = new Date(value);
									return date.toLocaleString();
								}}
							/>
						}
					/>
					<Line
						type="monotone"
						dataKey="completed"
						stroke="var(--color-completed)"
						strokeWidth={2}
						dot={false}
						activeDot={{ r: 4 }}
					/>
					<Line
						type="monotone"
						dataKey="failed"
						stroke="var(--color-failed)"
						strokeWidth={2}
						dot={false}
						activeDot={{ r: 4 }}
					/>
				</LineChart>
			</ChartContainer>
		</div>
	);
}
