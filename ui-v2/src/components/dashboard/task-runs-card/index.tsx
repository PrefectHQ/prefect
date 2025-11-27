import { useSuspenseQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import type { components } from "@/api/prefect";
import { buildListTaskRunsQuery, type TaskRunsFilter } from "@/api/task-runs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type StateType = components["schemas"]["StateType"];

type TaskRunsCardProps = {
	filter?: {
		startDate?: string;
		endDate?: string;
		tags?: string[];
	};
};

type TaskRunCounts = {
	total: number;
	running: number;
	completed: number;
	failed: number;
	completionPercentage: number;
	failurePercentage: number;
};

const calculateCounts = (
	taskRuns: Array<{ state_type: StateType }>,
): TaskRunCounts => {
	const total = taskRuns.length;
	const running = taskRuns.filter((tr) => tr.state_type === "RUNNING").length;
	const completed = taskRuns.filter(
		(tr) => tr.state_type === "COMPLETED",
	).length;
	const failed = taskRuns.filter(
		(tr) => tr.state_type === "FAILED" || tr.state_type === "CRASHED",
	).length;

	const completionPercentage = total > 0 ? (completed / total) * 100 : 0;
	const failurePercentage = total > 0 ? (failed / total) * 100 : 0;

	return {
		total,
		running,
		completed,
		failed,
		completionPercentage,
		failurePercentage,
	};
};

export function TaskRunsCard({ filter }: TaskRunsCardProps) {
	const taskRunsFilter: TaskRunsFilter = useMemo(() => {
		const baseFilter: TaskRunsFilter = {
			sort: "START_TIME_DESC",
			offset: 0,
		};

		const taskRunsFilterObj: NonNullable<TaskRunsFilter["task_runs"]> = {
			operator: "and_",
		};

		if (filter?.startDate && filter?.endDate) {
			taskRunsFilterObj.start_time = {
				after_: filter.startDate,
				before_: filter.endDate,
			};
		}

		if (filter?.tags && filter.tags.length > 0) {
			taskRunsFilterObj.tags = {
				operator: "and_",
				all_: filter.tags,
			};
		}

		if (Object.keys(taskRunsFilterObj).length > 1) {
			baseFilter.task_runs = taskRunsFilterObj;
		}

		return baseFilter;
	}, [filter?.startDate, filter?.endDate, filter?.tags]);

	const { data: taskRuns } = useSuspenseQuery(
		buildListTaskRunsQuery(taskRunsFilter, 30000),
	);

	const counts = useMemo(() => calculateCounts(taskRuns), [taskRuns]);

	return (
		<Card>
			<CardHeader>
				<CardTitle>Task Runs</CardTitle>
				{taskRuns.length > 0 && (
					<span className="text-sm text-muted-foreground">
						{counts.total} total
					</span>
				)}
			</CardHeader>
			<CardContent>
				{taskRuns.length === 0 ? (
					<div className="my-8 text-center text-sm text-muted-foreground">
						<p>No task runs found</p>
					</div>
				) : (
					<div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
						<div className="space-y-1">
							<p className="text-sm font-medium text-muted-foreground">
								Running
							</p>
							<p className="text-2xl font-bold">{counts.running}</p>
						</div>
						<div className="space-y-1">
							<p className="text-sm font-medium text-muted-foreground">
								Completed
							</p>
							<p className="text-2xl font-bold">{counts.completed}</p>
							<p className="text-xs text-muted-foreground">
								{counts.completionPercentage.toFixed(1)}%
							</p>
						</div>
						<div className="space-y-1">
							<p className="text-sm font-medium text-muted-foreground">
								Failed
							</p>
							<p className="text-2xl font-bold">{counts.failed}</p>
							<p className="text-xs text-muted-foreground">
								{counts.failurePercentage.toFixed(1)}%
							</p>
						</div>
						<div className="space-y-1">
							<p className="text-sm font-medium text-muted-foreground">Total</p>
							<p className="text-2xl font-bold">{counts.total}</p>
						</div>
					</div>
				)}
			</CardContent>
		</Card>
	);
}
