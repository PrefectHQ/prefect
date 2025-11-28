import { useMemo } from "react";
import type { TaskRun } from "@/api/task-runs";

type TaskRunStatsProps = {
	taskRuns: TaskRun[];
};

type TaskRunStatistics = {
	total: number;
	running: number;
	completed: number;
	failed: number;
	completedPercentage: number;
	failedPercentage: number;
};

export const TaskRunStats = ({ taskRuns }: TaskRunStatsProps) => {
	const stats = useMemo((): TaskRunStatistics => {
		const total = taskRuns.length;
		let running = 0;
		let completed = 0;
		let failed = 0;

		for (const tr of taskRuns) {
			const stateType = tr.state_type;
			if (!stateType) continue;

			if (stateType === "RUNNING") {
				running += 1;
			} else if (stateType === "COMPLETED") {
				completed += 1;
			} else if (stateType === "FAILED" || stateType === "CRASHED") {
				failed += 1;
			}
		}

		const totalFinished = completed + failed;
		const completedPercentage =
			totalFinished > 0 ? (completed / totalFinished) * 100 : 0;
		const failedPercentage =
			totalFinished > 0 ? (failed / totalFinished) * 100 : 0;

		return {
			total,
			running,
			completed,
			failed,
			completedPercentage,
			failedPercentage,
		};
	}, [taskRuns]);

	return (
		<div
			className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6"
			data-testid="task-run-stats"
		>
			<div className="space-y-1">
				<p className="text-sm font-medium text-muted-foreground">Total</p>
				<p className="text-2xl font-bold" data-testid="stat-total">
					{stats.total}
				</p>
			</div>
			<div className="space-y-1">
				<p className="text-sm font-medium text-muted-foreground">Running</p>
				<p className="text-2xl font-bold" data-testid="stat-running">
					{stats.running}
				</p>
			</div>
			<div className="space-y-1">
				<p className="text-sm font-medium text-muted-foreground">Completed</p>
				<p className="text-2xl font-bold" data-testid="stat-completed">
					{stats.completed}
				</p>
				<p
					className="text-xs text-muted-foreground"
					data-testid="stat-completed-percentage"
				>
					{stats.completedPercentage.toFixed(1)}%
				</p>
			</div>
			<div className="space-y-1">
				<p className="text-sm font-medium text-muted-foreground">Failed</p>
				<p className="text-2xl font-bold" data-testid="stat-failed">
					{stats.failed}
				</p>
				<p
					className="text-xs text-muted-foreground"
					data-testid="stat-failed-percentage"
				>
					{stats.failedPercentage.toFixed(1)}%
				</p>
			</div>
		</div>
	);
};
