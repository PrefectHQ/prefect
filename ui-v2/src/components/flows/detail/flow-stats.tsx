import { useSuspenseQueries } from "@tanstack/react-query";
import { useMemo } from "react";
import { buildCountFlowRunsByFlowPastWeekQuery } from "@/api/flow-runs";
import {
	buildCountTaskRunsQuery,
	type TaskRunsCountFilter,
} from "@/api/task-runs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type FlowStatsProps = {
	flowId: string;
};

const REFETCH_INTERVAL = 30_000;

export function FlowStats({ flowId }: FlowStatsProps) {
	const totalTaskRunsFilter: TaskRunsCountFilter = useMemo(
		() => ({
			flows: {
				operator: "and_",
				id: { any_: [flowId] },
			},
			task_runs: {
				operator: "and_",
				state: {
					operator: "and_",
					type: { any_: ["COMPLETED", "FAILED", "CRASHED", "RUNNING"] },
				},
			},
		}),
		[flowId],
	);

	const completedTaskRunsFilter: TaskRunsCountFilter = useMemo(
		() => ({
			flows: {
				operator: "and_",
				id: { any_: [flowId] },
			},
			task_runs: {
				operator: "and_",
				state: {
					operator: "and_",
					type: { any_: ["COMPLETED"] },
				},
			},
		}),
		[flowId],
	);

	const failedTaskRunsFilter: TaskRunsCountFilter = useMemo(
		() => ({
			flows: {
				operator: "and_",
				id: { any_: [flowId] },
			},
			task_runs: {
				operator: "and_",
				state: {
					operator: "and_",
					type: { any_: ["FAILED", "CRASHED"] },
				},
			},
		}),
		[flowId],
	);

	const [
		{ data: flowRunsCount },
		{ data: totalTaskRuns },
		{ data: completedTaskRuns },
		{ data: failedTaskRuns },
	] = useSuspenseQueries({
		queries: [
			buildCountFlowRunsByFlowPastWeekQuery(flowId, REFETCH_INTERVAL),
			buildCountTaskRunsQuery(totalTaskRunsFilter, REFETCH_INTERVAL),
			buildCountTaskRunsQuery(completedTaskRunsFilter, REFETCH_INTERVAL),
			buildCountTaskRunsQuery(failedTaskRunsFilter, REFETCH_INTERVAL),
		],
	});

	return (
		<div className="grid gap-4 md:grid-cols-4" data-testid="flow-stats">
			<Card>
				<CardHeader>
					<CardTitle className="text-sm font-medium text-muted-foreground">
						Flow Runs (Past Week)
					</CardTitle>
				</CardHeader>
				<CardContent>
					<p className="text-2xl font-bold" data-testid="flow-runs-count">
						{flowRunsCount}
					</p>
				</CardContent>
			</Card>
			<Card>
				<CardHeader>
					<CardTitle className="text-sm font-medium text-muted-foreground">
						Total Task Runs
					</CardTitle>
				</CardHeader>
				<CardContent>
					<p className="text-2xl font-bold" data-testid="total-task-runs">
						{totalTaskRuns}
					</p>
				</CardContent>
			</Card>
			<Card>
				<CardHeader>
					<CardTitle className="text-sm font-medium text-muted-foreground">
						Completed Task Runs
					</CardTitle>
				</CardHeader>
				<CardContent>
					<p className="text-2xl font-bold" data-testid="completed-task-runs">
						{completedTaskRuns}
					</p>
				</CardContent>
			</Card>
			<Card>
				<CardHeader>
					<CardTitle className="text-sm font-medium text-muted-foreground">
						Failed Task Runs
					</CardTitle>
				</CardHeader>
				<CardContent>
					<p className="text-2xl font-bold" data-testid="failed-task-runs">
						{failedTaskRuns}
					</p>
				</CardContent>
			</Card>
		</div>
	);
}
