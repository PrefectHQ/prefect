import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import {
	CartesianGrid,
	Line,
	LineChart,
	ResponsiveContainer,
	XAxis,
	YAxis,
} from "recharts";
import {
	buildCountTaskRunsQuery,
	buildGetTaskRunsHistoryQuery,
	type TaskRunsCountFilter,
	type TaskRunsHistoryFilter,
} from "@/api/task-runs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatisticKeyValue } from "./statistic-key-value";

type TaskRunsCardProps = {
	filter?: {
		startDate?: string;
		endDate?: string;
	};
};

export const TaskRunsCard = ({ filter }: TaskRunsCardProps) => {
	const allTasksFilter: TaskRunsCountFilter = useMemo(
		() => ({
			task_runs: {
				operator: "and_",
				state: {
					operator: "and_",
					type: {
						any_: ["COMPLETED", "FAILED", "CRASHED", "RUNNING"],
					},
				},
			},
		}),
		[],
	);

	const completedTasksFilter: TaskRunsCountFilter = useMemo(
		() => ({
			task_runs: {
				operator: "and_",
				state: {
					operator: "and_",
					type: {
						any_: ["COMPLETED"],
					},
				},
			},
		}),
		[],
	);

	const failedTasksFilter: TaskRunsCountFilter = useMemo(
		() => ({
			task_runs: {
				operator: "and_",
				state: {
					operator: "and_",
					type: {
						any_: ["FAILED", "CRASHED"],
					},
				},
			},
		}),
		[],
	);

	const runningTasksFilter: TaskRunsCountFilter = useMemo(
		() => ({
			task_runs: {
				operator: "and_",
				state: {
					operator: "and_",
					type: {
						any_: ["RUNNING"],
					},
				},
			},
		}),
		[],
	);

	const historyFilter: TaskRunsHistoryFilter = useMemo(() => {
		const now = new Date();
		const twentyFourHoursAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);

		const startDate = filter?.startDate
			? new Date(filter.startDate)
			: twentyFourHoursAgo;
		const endDate = filter?.endDate ? new Date(filter.endDate) : now;

		const timeSpanSeconds = (endDate.getTime() - startDate.getTime()) / 1000;
		const intervalSeconds = Math.max(1, Math.floor(timeSpanSeconds / 20));

		return {
			history_start: startDate.toISOString(),
			history_end: endDate.toISOString(),
			history_interval_seconds: intervalSeconds,
			task_runs: {
				operator: "and_",
				state: {
					operator: "and_",
					type: {
						any_: ["COMPLETED", "FAILED", "CRASHED"],
					},
				},
			},
		};
	}, [filter?.startDate, filter?.endDate]);

	const { data: totalCount } = useQuery(
		buildCountTaskRunsQuery(allTasksFilter),
	);
	const { data: completedCount } = useQuery(
		buildCountTaskRunsQuery(completedTasksFilter),
	);
	const { data: failedCount } = useQuery(
		buildCountTaskRunsQuery(failedTasksFilter),
	);
	const { data: runningCount } = useQuery(
		buildCountTaskRunsQuery(runningTasksFilter),
	);

	const { data: history } = useQuery(
		buildGetTaskRunsHistoryQuery(historyFilter),
	);

	const taskRunsChartData = useMemo(() => {
		if (!history || history.length === 0) {
			return { completed: [], failed: [] };
		}

		const completed: Array<{ timestamp: Date; value: number }> = [];
		const failed: Array<{ timestamp: Date; value: number }> = [];

		history.forEach((item) => {
			let completedCountInInterval = 0;
			let failedCountInInterval = 0;

			item.states.forEach((state) => {
				if (state.state_type === "COMPLETED") {
					completedCountInInterval += state.count_runs;
				} else if (
					state.state_type === "FAILED" ||
					state.state_type === "CRASHED"
				) {
					failedCountInInterval += state.count_runs;
				}
			});

			const completedBase =
				completed.length > 0 ? (completed.at(-1)?.value ?? 0) : 0;
			const failedBase = failed.length > 0 ? (failed.at(-1)?.value ?? 0) : 0;

			completed.push({
				timestamp: new Date(item.interval_start),
				value: completedBase + completedCountInInterval,
			});
			failed.push({
				timestamp: new Date(item.interval_start),
				value: failedBase + failedCountInInterval,
			});
		});

		return { completed, failed };
	}, [history]);

	const percentComparisonTotal = useMemo(() => {
		let comparisonTotal = totalCount ?? 0;

		if (runningCount) {
			comparisonTotal = comparisonTotal - runningCount;
		}

		return comparisonTotal;
	}, [totalCount, runningCount]);

	const completedPercentage = useMemo(() => {
		if (
			completedCount !== undefined &&
			percentComparisonTotal !== undefined &&
			percentComparisonTotal > 0
		) {
			const percent = Math.round(
				(completedCount / percentComparisonTotal) * 100,
			);
			return `${percent}%`;
		}
		return undefined;
	}, [completedCount, percentComparisonTotal]);

	const failedPercentage = useMemo(() => {
		if (
			failedCount !== undefined &&
			percentComparisonTotal !== undefined &&
			percentComparisonTotal > 0
		) {
			const percent = Math.round((failedCount / percentComparisonTotal) * 100);
			return `${percent}%`;
		}
		return undefined;
	}, [failedCount, percentComparisonTotal]);

	const maxValue = useMemo(() => {
		const completedValues = taskRunsChartData.completed.map((d) => d.value);
		const failedValues = taskRunsChartData.failed.map((d) => d.value);
		const minValue = 1;
		return Math.max(...completedValues, ...failedValues, minValue);
	}, [taskRunsChartData]);

	const MAX_ITERATIONS = 10;

	const maxCompletedValue = useMemo(() => {
		const completedValues = taskRunsChartData.completed.map((d) => d.value);
		const minValue = 1;
		const maxCompleted = Math.max(...completedValues, minValue);

		if (maxCompleted === maxValue) {
			return maxCompleted;
		}

		let unit = 1;

		while (unit <= MAX_ITERATIONS) {
			if (maxCompleted > maxValue / unit) {
				return maxCompleted * unit;
			}
			unit++;
		}

		return maxCompleted * unit;
	}, [taskRunsChartData, maxValue]);

	const maxFailedValue = useMemo(() => {
		const failedValues = taskRunsChartData.failed.map((d) => d.value);
		const minValue = 1;
		const maxFailed = Math.max(...failedValues, minValue);

		if (maxFailed === maxValue) {
			return maxFailed;
		}

		let unit = 1;

		while (unit <= MAX_ITERATIONS) {
			if (maxFailed > maxValue / unit) {
				return maxFailed * unit;
			}
			unit++;
		}

		return maxFailed * unit;
	}, [taskRunsChartData, maxValue]);

	const chartData = useMemo(() => {
		const maxLength = Math.max(
			taskRunsChartData.completed.length,
			taskRunsChartData.failed.length,
		);
		const data = [];

		for (let i = 0; i < maxLength; i++) {
			const completedPoint = taskRunsChartData.completed[i];
			const failedPoint = taskRunsChartData.failed[i];

			data.push({
				timestamp: completedPoint?.timestamp || failedPoint?.timestamp,
				completed: completedPoint?.value ?? 0,
				failed: failedPoint?.value ?? 0,
			});
		}

		return data;
	}, [taskRunsChartData]);

	return (
		<Card className="relative grid gap-4 auto-rows-max overflow-hidden pb-20">
			<CardHeader>
				<CardTitle>Task Runs</CardTitle>
			</CardHeader>
			<CardContent>
				<div className="grid gap-1">
					{totalCount !== undefined && (
						<StatisticKeyValue value={totalCount} primary />
					)}
					{runningCount !== undefined && runningCount > 0 && (
						<StatisticKeyValue
							value={runningCount}
							label="Running"
							className="text-blue-500"
						/>
					)}
					{completedCount !== undefined && (
						<StatisticKeyValue
							value={completedCount}
							label="Completed"
							meta={completedPercentage}
							className="text-green-600"
						/>
					)}
					{failedCount !== undefined && failedCount > 0 && (
						<StatisticKeyValue
							value={failedCount}
							label="Failed"
							meta={failedPercentage}
							className="text-red-700"
						/>
					)}
				</div>

				{/* Chart container */}
				<div className="absolute min-h-0 h-16 left-0 right-0 bottom-4">
					<ResponsiveContainer width="100%" height="100%">
						<LineChart data={chartData}>
							<CartesianGrid strokeDasharray="3 3" opacity={0.1} />
							<XAxis dataKey="timestamp" hide />
							<YAxis domain={[0, maxCompletedValue]} hide />
							<Line
								type="monotone"
								dataKey="completed"
								stroke="rgb(34 197 94)"
								strokeWidth={2}
								dot={false}
								isAnimationActive={false}
							/>
							{failedCount !== undefined && failedCount > 0 && (
								<>
									<YAxis domain={[0, maxFailedValue]} hide />
									<Line
										type="monotone"
										dataKey="failed"
										stroke="rgb(239 68 68)"
										strokeWidth={2}
										dot={false}
										isAnimationActive={false}
									/>
								</>
							)}
						</LineChart>
					</ResponsiveContainer>
				</div>
			</CardContent>
		</Card>
	);
};
