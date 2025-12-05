import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense, useMemo } from "react";
import {
	buildListTaskRunsQuery,
	type TaskRun,
	type TaskRunsFilter,
} from "@/api/task-runs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TaskRunsTrends } from "./task-runs-trends";

export { TaskRunStats } from "./task-runs-stats";
export { TaskRunsTrends } from "./task-runs-trends";

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

const calculateCounts = (taskRuns: TaskRun[]): TaskRunCounts => {
	const total = taskRuns.length;
	let running = 0;
	let completed = 0;
	let failed = 0;

	for (const run of taskRuns) {
		const stateType = run.state_type;
		if (!stateType) continue;

		if (stateType === "RUNNING") running += 1;
		else if (stateType === "COMPLETED") completed += 1;
		else if (stateType === "FAILED" || stateType === "CRASHED") failed += 1;
	}

	const totalFinished = completed + failed;
	const completionPercentage =
		totalFinished > 0 ? (completed / totalFinished) * 100 : 0;
	const failurePercentage =
		totalFinished > 0 ? (failed / totalFinished) * 100 : 0;

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
			sort: "ID_DESC",
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
			<CardHeader className="flex flex-row items-center justify-between">
				<CardTitle>Task Runs</CardTitle>
			</CardHeader>
			<CardContent>
				{taskRuns.length === 0 ? (
					<div className="my-8 text-center text-sm text-muted-foreground">
						<p>No task runs found</p>
					</div>
				) : (
					<div className="space-y-4">
						<div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
							<p className="text-3xl font-bold">{counts.total}</p>
							{counts.running > 0 && (
								<p className="text-sm">
									<span className="font-semibold text-blue-600">
										{counts.running}
									</span>{" "}
									<span className="text-muted-foreground">Running</span>
								</p>
							)}
							<p className="text-sm">
								<span className="font-semibold text-green-600">
									{counts.completed}
								</span>{" "}
								<span className="text-muted-foreground">
									Completed {counts.completionPercentage.toFixed(1)}%
								</span>
							</p>
							{counts.failed > 0 && (
								<p className="text-sm">
									<span className="font-semibold text-red-600">
										{counts.failed}
									</span>{" "}
									<span className="text-muted-foreground">
										Failed {counts.failurePercentage.toFixed(1)}%
									</span>
								</p>
							)}
						</div>
						<Suspense fallback={null}>
							<TaskRunsTrends filter={filter} />
						</Suspense>
					</div>
				)}
			</CardContent>
		</Card>
	);
}
