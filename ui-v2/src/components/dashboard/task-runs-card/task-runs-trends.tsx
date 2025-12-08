import { useSuspenseQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Area, AreaChart } from "recharts";
import {
	buildTaskRunsHistoryQuery,
	type HistoryResponse,
	type TaskRunsHistoryFilter,
} from "@/api/task-runs";
import { type ChartConfig, ChartContainer } from "@/components/ui/chart";

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

		// eslint-disable-next-line @typescript-eslint/no-unsafe-member-access, @typescript-eslint/no-unsafe-assignment
		const states = item.states;
		if (Array.isArray(states)) {
			for (const state of states) {
				// eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
				// eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
				if (state?.state_type === "COMPLETED") {
					// eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
					completedCount +=
						typeof state.count_runs === "number" ? state.count_runs : 0;
				} else if (
					// eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
					state?.state_type === "FAILED" ||
					// eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
					state?.state_type === "CRASHED"
				) {
					// eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
					failedCount +=
						typeof state.count_runs === "number" ? state.count_runs : 0;
				}
			}
		}

		cumulativeCompleted += completedCount;
		cumulativeFailed += failedCount;

		// eslint-disable-next-line @typescript-eslint/no-unsafe-member-access, @typescript-eslint/no-unsafe-assignment
		const intervalStart = item.interval_start;
		if (typeof intervalStart === "string") {
			chartData.push({
				timestamp: intervalStart,
				completed: cumulativeCompleted,
				failed: cumulativeFailed,
			});
		}
	}

	return chartData;
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
				operator: "and_",
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
				operator: "and_",
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
